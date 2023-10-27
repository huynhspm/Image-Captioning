from typing import Any, Dict, Optional, Tuple
from lightning.pytorch.utilities.types import STEP_OUTPUT

import wandb
import torch
from lightning import LightningModule
from torchmetrics import MaxMetric, MeanMetric
from torchmetrics.classification.accuracy import Accuracy
from pickle import load
import os.path as osp


class ImageCaptionModule(LightningModule):

    def __init__(
        self,
        net: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler,
        dataset_dir: str = 'data/flickr8k',
    ) -> None:
        """Initialize a `MNISTLitModule`.

        :param net: The model to train.
        :param optimizer: The optimizer to use for training.
        :param scheduler: The learning rate scheduler to use for training.
        """
        super().__init__()

        # this line allows to access init params with 'self.hparams' attribute
        # also ensures init params will be stored in ckpt
        self.save_hyperparameters(logger=False)

        self.net = net

        # loss function
        self.criterion = torch.nn.CrossEntropyLoss()

        vocab_size_path = osp.join(dataset_dir, 'vocab_size.pkl')
        if not osp.exists(vocab_size_path):
            raise ValueError(
                "weight_embedding_path is not exist. Please check path or run datamodule to prepare"
            )
        with open(vocab_size_path, "rb") as file:
            vocab_size = load(file)

        # metric objects for calculating and averaging accuracy across batches
        self.train_acc = Accuracy(task="multiclass", num_classes=vocab_size)
        self.val_acc = Accuracy(task="multiclass", num_classes=vocab_size)
        self.test_acc = Accuracy(task="multiclass", num_classes=vocab_size)

        # for averaging loss across batches
        self.train_loss = MeanMetric()
        self.val_loss = MeanMetric()
        self.test_loss = MeanMetric()

        # for tracking best so far validation accuracy
        self.val_acc_best = MaxMetric()

        self.images = {
            'train': [],
            'valid': [],
            'test': [],
        }

    def forward(self, image: torch.Tensor,
                sequence: torch.Tensor) -> torch.Tensor:
        """Perform a forward pass through the model `self.net`.

        :param x: A tensor of images.
        :return: A tensor of logits.
        """
        return self.net(image, sequence)

    def on_train_start(self) -> None:
        """Lightning hook that is called when training begins."""
        # by default lightning executes validation step sanity checks before training starts,
        # so it's worth to make sure validation metrics don't store results from these checks
        self.val_loss.reset()
        self.val_acc.reset()
        self.val_acc_best.reset()

    def model_step(
        self, batch: Tuple[torch.Tensor, torch.Tensor]
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Perform a single model step on a batch of data.

        :param batch: A batch of data (a tuple) containing the input tensor of images and target labels.

        :return: A tuple containing (in order):
            - A tensor of losses.
            - A tensor of predictions.
            - A tensor of target labels.
        """
        image, sequence, y = batch
        logits = self.forward(image, sequence)
        loss = self.criterion(logits, y)
        preds = torch.argmax(logits, dim=1)
        return loss, preds, y

    def training_step(self, batch: Tuple[torch.Tensor, torch.Tensor],
                      batch_idx: int) -> torch.Tensor:
        """Perform a single training step on a batch of data from the training set.

        :param batch: A batch of data (a tuple) containing the input tensor of images and target
            labels.
        :param batch_idx: The index of the current batch.
        :return: A tensor of losses between model predictions and targets.
        """
        loss, preds, targets = self.model_step(batch)

        # update and log metrics
        self.train_loss(loss)
        self.train_acc(preds, targets)
        self.log("train/loss",
                 self.train_loss,
                 on_step=False,
                 on_epoch=True,
                 prog_bar=True)
        self.log("train/acc",
                 self.train_acc,
                 on_step=False,
                 on_epoch=True,
                 prog_bar=True)

        # return loss or backpropagation will fail
        return loss

    def on_train_epoch_end(self) -> None:
        "Lightning hook that is called when a training epoch ends."
        return
        self.inference(mode='train')

    def validation_step(self, batch: Tuple[torch.Tensor, torch.Tensor],
                        batch_idx: int) -> None:
        """Perform a single validation step on a batch of data from the validation set.

        :param batch: A batch of data (a tuple) containing the input tensor of images and target
            labels.
        :param batch_idx: The index of the current batch.
        """
        loss, preds, targets = self.model_step(batch)

        # update and log metrics
        self.val_loss(loss)
        self.val_acc(preds, targets)
        self.log("val/loss",
                 self.val_loss,
                 on_step=False,
                 on_epoch=True,
                 prog_bar=True)
        self.log("val/acc",
                 self.val_acc,
                 on_step=False,
                 on_epoch=True,
                 prog_bar=True)

    def on_validation_epoch_end(self) -> None:
        "Lightning hook that is called when a validation epoch ends."
        acc = self.val_acc.compute()  # get current val acc
        self.val_acc_best(acc)  # update best so far val acc
        # log `val_acc_best` as a value through `.compute()` method, instead of as a metric object
        # otherwise metric would be reset by lightning after each epoch
        self.log("val/acc_best",
                 self.val_acc_best.compute(),
                 sync_dist=True,
                 prog_bar=True)

        self.inference(mode='val')

    def test_step(self, batch: Tuple[torch.Tensor, torch.Tensor],
                  batch_idx: int) -> None:
        """Perform a single test step on a batch of data from the test set.

        :param batch: A batch of data (a tuple) containing the input tensor of images and target
            labels.
        :param batch_idx: The index of the current batch.
        """
        loss, preds, targets = self.model_step(batch)

        # update and log metrics
        self.test_loss(loss)
        self.test_acc(preds, targets)
        self.log("test/loss",
                 self.test_loss,
                 on_step=False,
                 on_epoch=True,
                 prog_bar=True)
        self.log("test/acc",
                 self.test_acc,
                 on_step=False,
                 on_epoch=True,
                 prog_bar=True)

    def on_test_epoch_end(self) -> None:
        """Lightning hook that is called when a test epoch ends."""
        self.inference(mode='test')

    def setup(self, stage: str) -> None:
        """Lightning hook that is called at the beginning of fit (train + validate), validate,
        test, or predict.

        This is a good hook when you need to build models dynamically or adjust something about
        them. This hook is called on every process when using DDP.

        :param stage: Either `"fit"`, `"validate"`, `"test"`, or `"predict"`.
        """
        pass
        # if self.hparams.compile and stage == "fit":
        #     self.net = torch.compile(self.net)

    def configure_optimizers(self) -> Dict[str, Any]:
        """Choose what optimizers and learning-rate schedulers to use in your optimization.
        Normally you'd need one. But in the case of GANs or similar you might have multiple.

        Examples:
            https://lightning.ai/docs/pytorch/latest/common/lightning_module.html#configure-optimizers

        :return: A dict containing the configured optimizers and learning-rate schedulers to be used for training.
        """
        optimizer = self.hparams.optimizer(params=self.parameters())
        if self.hparams.scheduler is not None:
            scheduler = self.hparams.scheduler(optimizer=optimizer)
            return {
                "optimizer": optimizer,
                "lr_scheduler": {
                    "scheduler": scheduler,
                    "monitor": "val/loss",
                    "interval": "epoch",
                    "frequency": 1,
                },
            }
        return {"optimizer": optimizer}

    def on_train_batch_end(self, outputs: STEP_OUTPUT, batch: Any,
                           batch_idx: int) -> None:
        self.store_data(batch, mode='train')

    def on_validation_batch_end(self,
                                outputs: STEP_OUTPUT | None,
                                batch: Any,
                                batch_idx: int,
                                dataloader_idx: int = 0) -> None:
        self.store_data(batch, mode='val')

    def on_test_batch_end(self,
                          outputs: STEP_OUTPUT | None,
                          batch: Any,
                          batch_idx: int,
                          dataloader_idx: int = 0) -> None:
        self.store_data(batch, mode='test')

    def store_data(self, batch: Any, mode: str):
        self.images[mode] = batch[0]

    def inference(self, mode: str):
        data = []
        for img in self.images[mode][:4]:
            pred = self.net.greedySearch(img.unsqueeze(0))
            data.append([wandb.Image(img), pred])

        self.logger.log_table(key=f'{mode}/infer',
                              columns=['image', 'caption'],
                              data=data)


if __name__ == "__main__":
    import hydra
    from omegaconf import DictConfig
    import rootutils
    rootutils.setup_root(__file__, indicator=".project-root", pythonpath=True)

    root = rootutils.find_root(search_from=__file__, indicator=".project-root")
    print("root: ", root)
    config_path = str(root / "configs" / "model")

    @hydra.main(version_base=None,
                config_path=config_path,
                config_name="image_caption.yaml")
    def main(cfg: DictConfig):
        print(cfg)

        module: ImageCaptionModule = hydra.utils.instantiate(cfg)

        sequences = torch.randint(0, 100, (20, 2))
        images = torch.randn(2, 3, 299, 299)
        out = module.net(images, sequences)
        print(out.shape)

    main()