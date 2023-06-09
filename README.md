# Spiking-Based Transformer for Image Caption

Based on the network architecture of the __End-to-End Transformer Based Model for Image Captioning__ [[PDF/AAAI]](https://ojs.aaai.org/index.php/AAAI/article/view/20160) [[PDF/Arxiv]](https://arxiv.org/abs/2203.15350) [AAAI 2022], 
we designed a pulsed transformer for Image Caption and achieved competitive results, which is the first exploration and application of pulsed neural networks in the field of Image Caption.

中文介绍请参考[README_CN.md](README_CN.md)

![architecture](./imgs/architecture.png)

## Requirements (Our Main Enviroment)
+ Python 3.7.4
+ PyTorch 1.5.1
+ TorchVision 0.6.0
+ [coco-caption](https://github.com/tylin/coco-caption)
+ numpy
+ tqdm

## Preparation
### 1. coco-caption preparation
Refer coco-caption [README.md](./coco_caption/README.md), you will first need to download the [Stanford CoreNLP 3.6.0](http://stanfordnlp.github.io/CoreNLP/index.html) code and models for use by SPICE. To do this, run:
```bash
cd coco_caption
bash get_stanford_models.sh
```
### 2. Data preparation
The necessary files in training and evaluation are saved in __`mscoco`__ folder, which is organized as follows:
```
mscoco/
|--feature/
    |--coco2014/
       |--train2014/
       |--val2014/
       |--test2014/
       |--annotations/
|--misc/
|--sent/
|--txt/
```
where the `mscoco/feature/coco2014` folder contains the raw image and annotation files of [MSCOCO 2014](https://cocodataset.org/#download) dataset. You can download other files from [GoogleDrive](https://drive.google.com/drive/folders/1HBw5NGGw8DjkyNurksCP5v8a5f0FG7zU?usp=sharing) or [百度网盘](https://pan.baidu.com/s/1tyXGJx50sllS-zylN62ZAw)(提取码: hryh). 

__NOTE:__ You can also extract image features of MSCOCO 2014 using [Swin-Transformer](https://github.com/microsoft/Swin-Transformer) or others and save them as `***.npz` files into `mscoco/feature` for training speed up, refer to [coco_dataset.py](datasets/coco_dataset.py) and [data_loader.py](datasets/data_loader.py) for how to read and prepare features. 
__In this case, you need to make some modifications to [pure_transformer.py](models/pure_transformer.py) (delete the backbone module). For you smart and excellent people, I think it is an easy work.__


## Training
*Note: our repository is mainly based on [JDAI-CV/image-captioning](https://github.com/JDAI-CV/image-captioning), and we directly reused their config.yml files, so there are many useless parameter in our model. （__waiting for further sorting__）*

### 1. Training under XE loss
Download pre-trained Backbone model (Swin-Transformer) from [GoogleDrive](https://drive.google.com/drive/folders/1HBw5NGGw8DjkyNurksCP5v8a5f0FG7zU?usp=sharing) or [百度网盘](https://pan.baidu.com/s/1tyXGJx50sllS-zylN62ZAw)(提取码: hryh) and save it in the root directory.

Before training, you may need check and modify the parameters in `config.yml` and `train.sh` files. Then run the script:

```
# for XE training
bash experiments_PureT/PureT_XE/train.sh
```
### 2. Training using SCST (self-critical sequence training)
Copy the pre-trained model under XE loss into folder of `experiments_PureT/PureT_SCST/snapshot/` and modify `config.yml` and `train.sh` files. Then run the script:

```bash
# for SCST training
bash experiments_PureT/PureT_SCST/train.sh
```

## Evaluation
You can download the pre-trained model from [GoogleDrive](https://drive.google.com/drive/folders/1HBw5NGGw8DjkyNurksCP5v8a5f0FG7zU?usp=sharing) or [百度网盘](https://pan.baidu.com/s/1tyXGJx50sllS-zylN62ZAw)(提取码: hryh). 

```bash
CUDA_VISIBLE_DEVICES=0 python main_test.py --folder experiments_PureT/PureT_SCST/ --resume 30
```

|BLEU-1|BLEU-2|BLEU-3|BLEU-4|METEOR|ROUGE-L| CIDEr |SPICE |
| ---: | ---: | ---: | ---: | ---: | ---:  | ---:  | ---: |
| 80.2 | 64.4 | 49.63 | 37.6 | 28.34 | 58.15  | 128.01 |  21.83 |


[comment]: <> (## Reference)

[comment]: <> (If you find this repo useful, please consider citing &#40;no obligation at all&#41;:)

[comment]: <> (```)

[comment]: <> (@inproceedings{wangyiyu2022PureT,)

[comment]: <> (  title={End-to-End Transformer Based Model for Image Captioning},)

[comment]: <> (  author={Yiyu Wang and Jungang Xu and Yingfei Sun},)

[comment]: <> (  booktitle={AAAI},)

[comment]: <> (  year={2022})

[comment]: <> (})

[comment]: <> (```)

## Acknowledgements
This repository is based on [JDAI-CV/image-captioning](https://github.com/JDAI-CV/image-captioning), [ruotianluo/self-critical.pytorch](https://github.com/ruotianluo/self-critical.pytorch) and [microsoft/Swin-Transformer](https://github.com/microsoft/Swin-Transformer).
