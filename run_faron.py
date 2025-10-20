import os
import json
import argparse
from fire import fire

# from faron.


def main(mode:str,
         img_count:int):
    
    print("main")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FARON Data")

    parser.add_argument("--save_path",
                        help="Path to store the created dataset")

    parser.add_argument("--mode", choices=['polygon', 'map'], default='polygon',
                        help="Dataset mode (synthetic polygon or synthetic maps)")

    parser.add_argument("--n", default=5, 
                        help="Number of questions to create")

    args = parser.parse_args()

    #####################

    main(mode=args.mode
         img_count=args.n)