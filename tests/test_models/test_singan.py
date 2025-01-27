# Copyright (c) OpenMMLab. All rights reserved.
import pytest
import torch
from mmengine import MessageHub

from mmgen.core import SinGANOptimWrapperConstructor
from mmgen.models.gans.singan import PESinGAN, SinGAN
from mmgen.utils import register_all_modules

register_all_modules()


class TestSinGAN:

    @classmethod
    def setup_class(cls):
        cls.generator = dict(
            type='SinGANMultiScaleGenerator',
            in_channels=3,
            out_channels=3,
            num_scales=3)

        cls.disc = dict(
            type='SinGANMultiScaleDiscriminator', in_channels=3, num_scales=3)

        cls.data_preprocessor = dict(
            type='GANDataPreprocessor', non_image_keys=['input_sample'])
        cls.noise_weight_init = 0.1
        cls.curr_scale = -1
        cls.iters_per_scale = 2
        cls.lr_scheduler_args = dict(milestones=[1600], gamma=0.1)

        cls.data_batch = dict(
            real_scale0=torch.randn(1, 3, 25, 25),
            real_scale1=torch.randn(1, 3, 30, 30),
            real_scale2=torch.randn(1, 3, 32, 32),
        )
        cls.data_batch['input_sample'] = torch.zeros_like(
            cls.data_batch['real_scale0'])

        cls.optim_wrapper_cfg = dict(
            generator=dict(
                optimizer=dict(type='Adam', lr=0.0005, betas=(0.5, 0.999))),
            discriminator=dict(
                optimizer=dict(type='Adam', lr=0.0005, betas=(0.5, 0.999))))

    def test_singan_cpu(self):
        message_hub = MessageHub.get_instance('mmgen')
        message_hub.update_info('iter', 0)

        singan = SinGAN(
            self.generator,
            self.disc,
            num_scales=3,
            data_preprocessor=self.data_preprocessor,
            noise_weight_init=self.noise_weight_init,
            iters_per_scale=self.iters_per_scale,
            lr_scheduler_args=self.lr_scheduler_args)
        optim_wrapper_dict_builder = SinGANOptimWrapperConstructor(
            self.optim_wrapper_cfg)
        optim_wrapper_dict = optim_wrapper_dict_builder(singan)

        for i in range(6):
            singan.train_step(self.data_batch, optim_wrapper_dict)
            message_hub.update_info('iter', message_hub.get_info('iter') + 1)
            outputs = singan.forward(dict(num_batches=1), None)

            img = torch.stack([out.fake_img.data for out in outputs], dim=0)
            if i in [0, 1]:
                assert singan.curr_stage == 0
                assert img.shape[-2:] == (25, 25)
            elif i in [2, 3]:
                assert singan.curr_stage == 1
                assert img.shape[-2:] == (30, 30)
            elif i in [4, 5]:
                assert singan.curr_stage == 2
                assert img.shape[-2:] == (32, 32)

        # test val step
        with pytest.raises(NotImplementedError):
            singan.val_step(None)


class TestPESinGAN:

    @classmethod
    def setup_class(cls):
        cls.generator = dict(
            type='SinGANMSGeneratorPE',
            in_channels=3,
            out_channels=3,
            num_scales=3,
            interp_pad=True,
            noise_with_pad=True)

        cls.disc = dict(
            type='SinGANMultiScaleDiscriminator', in_channels=3, num_scales=3)

        cls.data_preprocessor = dict(
            type='GANDataPreprocessor', non_image_keys=['input_sample'])

        cls.noise_weight_init = 0.1
        cls.iters_per_scale = 2
        cls.disc_steps = 3
        cls.generator_steps = 3
        cls.fixed_noise_with_pad = True
        cls.lr_scheduler_args = dict(milestones=[1600], gamma=0.1)

        cls.data_batch = dict(
            real_scale0=torch.randn(1, 3, 25, 25),
            real_scale1=torch.randn(1, 3, 30, 30),
            real_scale2=torch.randn(1, 3, 32, 32),
        )
        cls.data_batch['input_sample'] = torch.zeros_like(
            cls.data_batch['real_scale0'])

        cls.optim_wrapper_cfg = dict(
            generator=dict(
                optimizer=dict(type='Adam', lr=0.0005, betas=(0.5, 0.999))),
            discriminator=dict(
                optimizer=dict(type='Adam', lr=0.0005, betas=(0.5, 0.999))))

    def test_pesingan_cpu(self):
        message_hub = MessageHub.get_instance('mmgen')
        message_hub.update_info('iter', 0)
        singan = PESinGAN(
            self.generator,
            self.disc,
            num_scales=3,
            data_preprocessor=self.data_preprocessor,
            noise_weight_init=self.noise_weight_init,
            iters_per_scale=self.iters_per_scale,
            lr_scheduler_args=self.lr_scheduler_args,
            fixed_noise_with_pad=self.fixed_noise_with_pad)

        optim_wrapper_dict_builder = SinGANOptimWrapperConstructor(
            self.optim_wrapper_cfg)
        optim_wrapper_dict = optim_wrapper_dict_builder(singan)

        for i in range(6):
            singan.train_step(self.data_batch, optim_wrapper_dict)
            message_hub.update_info('iter', message_hub.get_info('iter') + 1)
            # img = singan.forward(dict(num_batches=1), None)

            # if i in [0, 1]:
            #     assert singan.curr_stage == 0
            #     assert img.shape[-2:] == (25, 25)
            # elif i in [2, 3]:
            #     assert singan.curr_stage == 1
            #     assert img.shape[-2:] == (30, 30)
            # elif i in [4, 5]:
            #     assert singan.curr_stage == 2
            #     assert img.shape[-2:] == (32, 32)

        singan = PESinGAN(
            dict(
                type='SinGANMSGeneratorPE',
                in_channels=3,
                out_channels=3,
                num_scales=3,
                interp_pad=True,
                noise_with_pad=False),
            self.disc,
            num_scales=3,
            data_preprocessor=self.data_preprocessor,
            noise_weight_init=0.1,
            iters_per_scale=2,
            discriminator_steps=1,
            generator_steps=1,
            lr_scheduler_args=dict(milestones=[1600], gamma=0.1),
            fixed_noise_with_pad=False)
        optim_wrapper_dict_builder = SinGANOptimWrapperConstructor(
            self.optim_wrapper_cfg)
        optim_wrapper_dict = optim_wrapper_dict_builder(singan)

        message_hub.update_info('iter', 0)
        for i in range(6):
            singan.train_step(self.data_batch, optim_wrapper_dict)
            message_hub.update_info('iter', message_hub.get_info('iter') + 1)
            outputs = singan.forward(dict(num_batches=1), None)
            img = torch.stack([out.fake_img.data for out in outputs])
            if i in [0, 1]:
                assert singan.curr_stage == 0
                assert img.shape[-2:] == (25, 25)
            elif i in [2, 3]:
                assert singan.curr_stage == 1
                assert img.shape[-2:] == (30, 30)
            elif i in [4, 5]:
                assert singan.curr_stage == 2
                assert img.shape[-2:] == (32, 32)
