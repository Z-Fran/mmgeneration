# Copyright (c) OpenMMLab. All rights reserved.
from copy import deepcopy
from unittest import TestCase

import torch
from mmcls.data import ClsDataSample
from mmengine import MessageHub
from mmengine.optim import OptimWrapper, OptimWrapperDict
from torch.optim import SGD

from mmgen.models import BigGAN, GANDataPreprocessor
from mmgen.models.builder import build_module

generator = dict(
    type='BigGANGenerator',
    output_scale=32,
    noise_size=128,
    num_classes=10,
    base_channels=64,
    with_shared_embedding=False,
    sn_eps=1e-8,
    sn_style='torch',
    init_type='N02',
    split_noise=False,
    auto_sync_bn=False)
discriminator = dict(
    type='BigGANDiscriminator',
    input_scale=32,
    num_classes=10,
    base_channels=64,
    sn_eps=1e-8,
    sn_style='torch',
    init_type='N02',
    with_spectral_norm=True)


class TestBigGAN(TestCase):

    def test_init(self):
        gan = BigGAN(
            num_classes=10,
            data_preprocessor=GANDataPreprocessor(),
            generator=generator,
            discriminator=discriminator,
            generator_steps=1,
            discriminator_steps=4)

        self.assertIsInstance(gan, BigGAN)
        self.assertIsInstance(gan.data_preprocessor, GANDataPreprocessor)

        # test only generator have noise size
        gen_cfg = deepcopy(generator)
        gen_cfg['noise_size'] = 10
        gan = BigGAN(
            noise_size=10,
            generator=gen_cfg,
            discriminator=discriminator,
            data_preprocessor=GANDataPreprocessor())
        self.assertEqual(gan.noise_size, 10)

        # test init with nn.Module
        gen_cfg = deepcopy(generator)
        gen_cfg['noise_size'] = 10
        disc_cfg = deepcopy(discriminator)
        gen = build_module(gen_cfg)
        disc = build_module(disc_cfg)
        gan = BigGAN(
            generator=gen,
            discriminator=disc,
            data_preprocessor=GANDataPreprocessor())
        self.assertEqual(gan.generator, gen)
        self.assertEqual(gan.discriminator, disc)

        # test init without discriminator
        gan = BigGAN(generator=gen, data_preprocessor=GANDataPreprocessor())
        self.assertEqual(gan.discriminator, None)

        # test init with different num_classes
        gan = BigGAN(
            num_classes=10,
            data_preprocessor=GANDataPreprocessor(),
            generator=generator,
            discriminator=discriminator,
            generator_steps=1,
            discriminator_steps=4)

    def test_train_step(self):
        # prepare model
        accu_iter = 1
        n_disc = 1
        message_hub = MessageHub.get_instance('mmgen')
        gan = BigGAN(
            generator=generator,
            discriminator=discriminator,
            data_preprocessor=GANDataPreprocessor(),
            discriminator_steps=n_disc)
        # prepare messageHub
        message_hub.update_info('iter', 0)
        # prepare optimizer
        gen_optim = SGD(gan.generator.parameters(), lr=0.1)
        disc_optim = SGD(gan.discriminator.parameters(), lr=0.1)
        optim_wrapper_dict = OptimWrapperDict(
            generator=OptimWrapper(gen_optim, accumulative_counts=accu_iter),
            discriminator=OptimWrapper(
                disc_optim, accumulative_counts=accu_iter))
        # prepare inputs
        img = torch.randn(3, 16, 16)
        label = torch.randint(0, 10, (3, 1))

        data_sample = ClsDataSample()
        data_sample.set_gt_label(label)

        data = dict(inputs=img, data_sample=data_sample)

        # simulate train_loop here
        for idx in range(n_disc * accu_iter):
            message_hub.update_info('iter', idx)
            log = gan.train_step([data], optim_wrapper_dict)
            if (idx + 1) == n_disc * accu_iter:
                # should update at after (n_disc * accu_iter)
                self.assertEqual(
                    set(log.keys()),
                    set([
                        'loss', 'loss_disc_fake', 'loss_disc_real', 'loss_gen'
                    ]))
            else:
                # should not update when discriminator's updating is unfinished
                self.assertEqual(
                    log.keys(),
                    set(['loss', 'loss', 'loss_disc_fake', 'loss_disc_real']))
