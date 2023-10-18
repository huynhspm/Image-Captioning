import torch
import torch.nn as nn
from torch import Tensor
from pickle import load
import os.path as osp


class Glove_LSTM(nn.Module):

    def __init__(
        self,
        embed_dim: int = 200,
        text_features: int = 256,
        n_layer_lstm: int = 1,
        weight_embedding_path: str = 'data/flickr8k/embedding_matrix.pkl',
    ) -> None:
        super().__init__()

        self.embed = nn.Embedding.from_pretrained(
            self.load_weight_embedding(weight_embedding_path))
        self.dropout = nn.Dropout(p=0.5)
        self.lstm = nn.LSTM(input_size=embed_dim,
                            hidden_size=text_features,
                            num_layers=n_layer_lstm,
                            batch_first=False)

    def load_weight_embedding(self, weight_embedding_path: str):
        if not osp.exists(weight_embedding_path):
            raise ValueError(
                "weight_embedding_path is not exist. Please check path or run datamodule to prepare"
            )

        with open(weight_embedding_path, "rb") as file:
            embedding_matrix = load(file)
        print('Embedding_matrix:', embedding_matrix.shape)
        return embedding_matrix

    def forward(self, sequence: Tensor) -> Tensor:
        out = self.embed(sequence)
        out = self.dropout(out)
        out, _ = self.lstm(out)  # return output and hidden state
        return out[-1]  # only get


if __name__ == "__main__":
    net = Glove_LSTM()

    x = torch.randint(0, 100, (20, 2))
    out = net(x)
    print(out.shape)