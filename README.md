# Data Efficient Stagewise Knowledge Distillation

Note: A new version of this paper based on semantic segmentation and image classification results will be released soon. The previous version described only the image classification results. This repo will soon be updated with details of the new experiments (code is already uploaded).

![Stagewise Training Procedure](/image_classification/figures/training_proc.png)

## Code Implementation for [Stagewise Knowledge Distillation](https://arxiv.org/abs/1911.06786)
This repository presents the code implementation for [Stagewise Knowledge Distillation](https://arxiv.org/abs/1911.06786), a technique for improving knowledge transfer between a teacher model and student model.

### Dependencies
- [PyTorch 1.3.0](https://pytorch.org/)
- [fastai v1](https://github.com/fastai/fastai/blob/master/README.md#installation)

### Architectures Used
Following [ResNet](https://arxiv.org/abs/1512.03385) architectures are used:
- ResNet - {10, 14, 18, 20, 26, 34}

Note: ResNet34 is used as a teacher (being a standard architecture), while others are used as student models.

### Datasets Used
- [CIFAR10](https://www.cs.toronto.edu/~kriz/cifar.html)
- [Imagenette](https://github.com/fastai/imagenette)
- [Imagewoof](https://github.com/fastai/imagenette)

Note: Imagenette and Imagewoof are subsets of ImageNet.

### Code Organization 
- `root/code/models/` - Contains code for models.
- `root/code/create_dataset.py` - Code for modifying dataset to get smaller sized dataset.
- `root/code/medium.py` - Code for simultaneous training of all stages on complete dataset
- `root/code/stagewise_medium.py` - Code for stagewise training on complete dataset.
- `root/code/less_data_stagewise_medium.py` - Code for stagewise training on smaller sized dataset.
- `root/code/utils.py` - Some utility code.
- `root/notebooks/` - Contains notebooks with similar code as above.

## Citation
If you use this code or method in your work, please cite using
```
@misc{kulkarni2019stagewise,
    title={Stagewise Knowledge Distillation},
    author={Akshay Kulkarni and Navid Panchi and Shital Chiddarwar},
    year={2019},
    eprint={1911.06786},
    archivePrefix={arXiv},
    primaryClass={cs.LG}
}
```
