import os

from torch.utils.data import Dataset
from faron.utils import *

class FARON(Dataset):
    def __init__(self,
                 save_dir:str,
                 mode:str,
                 img_count:int) -> None:
        
        self.save_dir = save_dir
        self.img_count = img_count

        self.data = []
        if mode == 'polygon':
            print("[INFO] Polygon")

        elif mode == 'map':
            print("[INFO] Maps")

        else:
            print("[INFO] Mix")

        

    def create_ds_polygon(img_count:int):
        return 0
    
    def create_ds_map(img_count:int):
        return 0
    