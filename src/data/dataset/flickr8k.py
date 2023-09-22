import re
import imageio
import pandas as pd
import os.path as osp
from torch.utils.data import Dataset


class FlickrDataset8k(Dataset):

    dataset_dir = 'flickr8k'
    dataset_url = 'https://www.kaggle.com/datasets/adityajn105/flickr8k'

    def __init__(self,
                 data_dir: str = 'data') -> None:
        """
            data_dir:
        """
        super().__init__()

        self.dataset_dir = osp.join(data_dir, self.dataset_dir)
        self.df = pd.read_csv(osp.join(self.dataset_dir, 'captions.txt'))
        self.df['caption'] = self.df['caption'].apply(caption_preprocessing)

    def prepare_data(self) -> None:
        pass

    def __len__(self):
        return len(self.df) // 5

    def __getitem__(self, index):
        index *= 5
        captions = [self.df['caption'][index + i] for i in range(5)]
        img_path = osp.join(self.dataset_dir, 'Images', self.df['image'][index])    
        return img_path, captions
    
def caption_preprocessing(text):
    # removw punctuation
    pattern=r'[^a-zA-z0-9\s]'
    text=re.sub(pattern,'',text)

    # tokenize
    text=text.split()
    # convert to lower case
    text = [word.lower() for word in text]

    # remove tokens with numbers in them
    text = [word for word in text if word.isalpha()]
    # concat string
    text =  ' '.join(text)

    # insert 'startseq', 'endseq'
    text = 'startseq ' + text + ' endseq'
    return text

if __name__ == "__main__":
    dataset = FlickrDataset8k()
    print(len(dataset))
    
    img_path, captions = dataset[0]
    image = imageio.v2.imread(img_path)
    print('Image size:', image.shape)
    print('Caption:', captions)
    
    import matplotlib.pyplot as plt
    plt.imshow(image)
    plt.show()