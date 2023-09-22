from .flickr8k import FlickrDataset8k
from .flickr30k import FlickrDataset30k

__datasets = {
    'flickr8k': FlickrDataset8k,
    'flickr30k': FlickrDataset30k,
}


def init_dataset(name, **kwargs):
    """Initializes a dataset."""
    avai_datasets = list(__datasets.keys())
    if name not in avai_datasets:
        raise ValueError('Invalid dataset name. Received "{}", '
                         'but expected to be one of {}'.format(
                             name, avai_datasets))
    return __datasets[name](**kwargs)