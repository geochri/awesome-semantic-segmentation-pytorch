import os
import torch
import torch.nn as nn
import torch.nn.functional as F

from models.vgg import vgg16
from models.utils import weights_init
from models.model_store import get_model_file

__all__ = ['get_fcn32s', 'get_fcn16s', 'get_fcn8s',
           'get_fcn32s_vgg16_voc', 'get_fcn16s_vgg16_voc', 'get_fcn8s_vgg16_voc']


class FCN32s(nn.Module):
    """There are some difference from original fcn"""

    def __init__(self, nclass, backbone='vgg16', aux=False, pretrained_base=True,
                 base_size=520, crop_size=480, **kwargs):
        super(FCN32s, self).__init__()
        self.aux = aux
        if backbone == 'vgg16':
            self.features = vgg16(pretrained=pretrained_base).features
        else:
            raise RuntimeError('unknown backbone: {}'.format(backbone))
        self.head = _FCNHead(512, nclass)
        if aux:
            self.auxlayer = _FCNHead(512, nclass)

    def forward(self, x):
        pool5 = self.features(x)

        outputs = []
        out = self.head(pool5)
        out = F.interpolate(out, x.size()[2:], mode='bilinear', align_corners=True)
        outputs.append(out)

        if self.aux:
            auxout = self.auxlayer(pool5)
            auxout = F.interpolate(auxout, x.size()[2:], mode='bilinear', align_corners=True)
            outputs.append(auxout)

        return tuple(outputs)

    def _initialize_weights(self):
        self.head.apply(weights_init)


class FCN16s(nn.Module):
    def __init__(self, nclass, backbone='vgg16', aux=False, pretrained_base=True, base_size=520, crop_size=480, **kwargs):
        super(FCN16s, self).__init__()
        self.aux = aux
        if backbone == 'vgg16':
            self.features = vgg16(pretrained=pretrained_base).features
        else:
            raise RuntimeError('unknown backbone: {}'.format(backbone))
        self.pool4 = nn.Sequential(*self.features[:24])
        self.pool5 = nn.Sequential(*self.features[24:])
        self.head = _FCNHead(512, nclass)
        self.score_pool4 = nn.Conv2d(512, nclass, 1)
        if aux:
            self.auxlayer = _FCNHead(512, nclass)

    def forward(self, x):
        pool4 = self.pool4(x)
        pool5 = self.pool5(pool4)

        outputs = []
        score_fr = self.head(pool5)

        score_pool4 = self.score_pool4(pool4)

        upscore2 = F.interpolate(score_fr, score_pool4.size()[2:], mode='bilinear', align_corners=True)
        fuse_pool4 = upscore2 + score_pool4

        out = F.interpolate(fuse_pool4, x.size()[2:], mode='bilinear', align_corners=True)
        outputs.append(out)

        if self.aux:
            auxout = self.auxlayer(pool5)
            auxout = F.interpolate(auxout, x.size()[2:], mode='bilinear', align_corners=True)
            outputs.append(auxout)

        return tuple(outputs)

    def _initialize_weights(self):
        self.head.apply(weights_init)
        self.score_pool4.apply(weights_init)


class FCN8s(nn.Module):
    def __init__(self, nclass, backbone='vgg16', aux=False, pretrained_base=True, base_size=520, crop_size=480, **kwargs):
        super(FCN8s, self).__init__()
        self.aux = aux
        if backbone == 'vgg16':
            self.features = vgg16(pretrained=pretrained_base).features
        else:
            raise RuntimeError('unknown backbone: {}'.format(backbone))
        self.pool3 = nn.Sequential(*self.features[:17])
        self.pool4 = nn.Sequential(*self.features[17:24])
        self.pool5 = nn.Sequential(*self.features[24:])
        self.head = _FCNHead(512, nclass)
        self.score_pool3 = nn.Conv2d(256, nclass, 1)
        self.score_pool4 = nn.Conv2d(512, nclass, 1)
        if aux:
            self.auxlayer = _FCNHead(512, nclass)

    def forward(self, x):
        pool3 = self.pool3(x)
        pool4 = self.pool4(pool3)
        pool5 = self.pool5(pool4)

        outputs = []
        score_fr = self.head(pool5)

        score_pool4 = self.score_pool4(pool4)
        score_pool3 = self.score_pool3(pool3)

        upscore2 = F.interpolate(score_fr, score_pool4.size()[2:], mode='bilinear', align_corners=True)
        fuse_pool4 = upscore2 + score_pool4

        upscore_pool4 = F.interpolate(fuse_pool4, score_pool3.size()[2:], mode='bilinear', align_corners=True)
        fuse_pool3 = upscore_pool4 + score_pool3

        out = F.interpolate(fuse_pool3, x.size()[2:], mode='bilinear', align_corners=True)
        outputs.append(out)

        if self.aux:
            auxout = self.auxlayer(pool5)
            auxout = F.interpolate(auxout, x.size()[2:], mode='bilinear', align_corners=True)
            outputs.append(auxout)

        return tuple(outputs)

    def _initialize_weights(self):
        self.head.apply(weights_init)
        self.score_pool4.apply(weights_init)
        self.score_pool3.apply(weights_init)


class _FCNHead(nn.Module):
    def __init__(self, in_channels, channels, **kwargs):
        super(_FCNHead, self).__init__()
        inter_channels = in_channels // 4
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, inter_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(inter_channels),
            nn.ReLU(inplace=True),
            nn.Dropout(0.1),
            nn.Conv2d(inter_channels, channels, 1)
        )

    def forward(self, x):
        return self.block(x)


def get_fcn32s(dataset='pascal_voc', backbone='vgg16', pretrained=False, root='~/.torch/models',
               pretrained_base=True, **kwargs):
    acronyms = {
        'pascal_voc': 'pascal_voc',
        'pascal_aug': 'pascal_aug',
        'ade20k': 'ade',
        'coco': 'coco',
        'citys': 'citys',
    }
    from data_loader import datasets
    model = FCN32s(datasets[dataset].NUM_CLASS, backbone=backbone, pretrained_base=pretrained_base, **kwargs)
    if pretrained:
        model.load_state_dict(torch.load(get_model_file('fcn32s_%s_%s' % (backbone, acronyms[dataset]), root=root)))
    return model


def get_fcn16s(dataset='pascal_voc', backbone='vgg16', pretrained=False, root='~/.torch/models',
               pretrained_base=True, **kwargs):
    acronyms = {
        'pascal_voc': 'pascal_voc',
        'pascal_aug': 'pascal_aug',
        'ade20k': 'ade',
        'coco': 'coco',
        'citys': 'citys',
    }
    from data_loader import datasets
    model = FCN16s(datasets[dataset].NUM_CLASS, backbone=backbone, pretrained_base=pretrained_base, **kwargs)
    if pretrained:
        model.load_state_dict(torch.load(get_model_file('fcn32s_%s_%s' % (backbone, acronyms[dataset]), root=root)))
    return model


def get_fcn8s(dataset='pascal_voc', backbone='vgg16', pretrained=False, root='~/.torch/models',
              pretrained_base=True, **kwargs):
    acronyms = {
        'pascal_voc': 'pascal_voc',
        'pascal_aug': 'pascal_aug',
        'ade20k': 'ade',
        'coco': 'coco',
        'citys': 'citys',
    }
    from data_loader import datasets
    model = FCN8s(datasets[dataset].NUM_CLASS, backbone=backbone, pretrained_base=pretrained_base, **kwargs)
    if pretrained:
        model.load_state_dict(torch.load(get_model_file('fcn32s_%s_%s' % (backbone, acronyms[dataset]), root=root)))
    return model


def get_fcn32s_vgg16_voc(**kwargs):
    return get_fcn32s('pascal_voc', 'vgg16', **kwargs)


def get_fcn16s_vgg16_voc(**kwargs):
    return get_fcn16s('pascal_voc', 'vgg16', **kwargs)


def get_fcn8s_vgg16_voc(**kwargs):
    return get_fcn8s('pascal_voc', 'vgg16', **kwargs)
