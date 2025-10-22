import os
import json
import argparse
from fire import fire

from faron import FARON

def main(save_dir:str,
         
         mode:str,
         img_count:int):
    
    FARON(save_dir=save_dir,
          mode=mode,
          img_count=img_count)
    
    print("main")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FARON Data")

    parser.add_argument("--save_path", default='./data'
                        help="Path to store the created dataset")

    parser.add_argument("--mode", choices=['polygon', 'map', 'mix'], default='polygon',
                        help="Dataset mode (synthetic polygon or synthetic maps)")

    parser.add_argument("--n", default=5, 
                        help="Number of questions to create")

    args = parser.parse_args()

    #####################

    main(save_dir=args.save_path,
         mode=args.mode,
         img_count=args.n)