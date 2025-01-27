# Copyright (c) OpenMMLab. All rights reserved.
import copy

import torch
from mmcv.runner import obj_from_dict
from mmengine import MessageHub
from mmengine.optim import OptimWrapper, OptimWrapperDict

from mmgen.models import (CycleGAN, GANDataPreprocessor, PatchDiscriminator,
                          ResnetGenerator)


def test_cyclegan():

    model_cfg = dict(
        default_domain='photo',
        reachable_domains=['photo', 'mask'],
        related_domains=['photo', 'mask'],
        generator=dict(
            type='ResnetGenerator',
            in_channels=3,
            out_channels=3,
            base_channels=64,
            norm_cfg=dict(type='IN'),
            use_dropout=False,
            num_blocks=9,
            padding_mode='reflect',
            init_cfg=dict(type='normal', gain=0.02)),
        discriminator=dict(
            type='PatchDiscriminator',
            in_channels=3,
            base_channels=64,
            num_conv=3,
            norm_cfg=dict(type='IN'),
            init_cfg=dict(type='normal', gain=0.02)))

    train_settings = None

    # build synthesizer
    synthesizer = CycleGAN(
        **model_cfg, data_preprocessor=GANDataPreprocessor())

    # test attributes
    assert synthesizer.__class__.__name__ == 'CycleGAN'
    assert isinstance(synthesizer.generators['photo'], ResnetGenerator)
    assert isinstance(synthesizer.generators['mask'], ResnetGenerator)
    assert isinstance(synthesizer.discriminators['photo'], PatchDiscriminator)
    assert isinstance(synthesizer.discriminators['mask'], PatchDiscriminator)

    # prepare data
    inputs = torch.rand(1, 3, 64, 64)
    targets = torch.rand(1, 3, 64, 64)
    data_batch = {'img_mask': inputs, 'img_photo': targets}

    # prepare optimizer
    optim_cfg = dict(type='Adam', lr=2e-4, betas=(0.5, 0.999))
    optimizer = OptimWrapperDict(
        generators=OptimWrapper(
            obj_from_dict(
                optim_cfg, torch.optim,
                dict(params=getattr(synthesizer, 'generators').parameters()))),
        discriminators=OptimWrapper(
            obj_from_dict(
                optim_cfg, torch.optim,
                dict(
                    params=getattr(synthesizer,
                                   'discriminators').parameters()))))

    # test forward_test
    with torch.no_grad():
        outputs = synthesizer(inputs, target_domain='photo', test_mode=True)
    assert torch.equal(outputs['source'], data_batch['img_mask'])
    assert torch.is_tensor(outputs['target'])
    assert outputs['target'].size() == (1, 3, 64, 64)

    with torch.no_grad():
        outputs = synthesizer(targets, target_domain='mask', test_mode=True)
    assert torch.equal(outputs['source'], data_batch['img_photo'])
    assert torch.is_tensor(outputs['target'])
    assert outputs['target'].size() == (1, 3, 64, 64)

    # test forward_train
    with torch.no_grad():
        outputs = synthesizer(inputs, target_domain='photo', test_mode=True)
    assert torch.equal(outputs['source'], data_batch['img_mask'])
    assert torch.is_tensor(outputs['target'])
    assert outputs['target'].size() == (1, 3, 64, 64)

    with torch.no_grad():
        outputs = synthesizer(targets, target_domain='mask', test_mode=True)
    assert torch.equal(outputs['source'], data_batch['img_photo'])
    assert torch.is_tensor(outputs['target'])
    assert outputs['target'].size() == (1, 3, 64, 64)

    # test train_step
    message_hub = MessageHub.get_instance('mmgen')
    message_hub.update_info('iter', 0)
    inputs = torch.rand(3, 64, 64)
    targets = torch.rand(3, 64, 64)
    data_batch = [dict(inputs={'img_mask': inputs, 'img_photo': targets})]
    log_vars = synthesizer.train_step(data_batch, optimizer)
    assert isinstance(log_vars, dict)
    for v in [
            'loss_gan_d_mask', 'loss_gan_d_photo', 'loss_gan_g_mask',
            'loss_gan_g_photo', 'cycle_loss', 'id_loss'
    ]:
        assert isinstance(log_vars[v].item(), float)

    # test train_step and forward_test (gpu)
    if torch.cuda.is_available():
        synthesizer = synthesizer.cuda()
        optimizer = OptimWrapperDict(
            generators=OptimWrapper(
                obj_from_dict(
                    optim_cfg, torch.optim,
                    dict(
                        params=getattr(synthesizer,
                                       'generators').parameters()))),
            discriminators=OptimWrapper(
                obj_from_dict(
                    optim_cfg, torch.optim,
                    dict(
                        params=getattr(synthesizer,
                                       'discriminators').parameters()))))

        inputs = torch.rand(1, 3, 64, 64)
        targets = torch.rand(1, 3, 64, 64)
        data_batch = {'img_mask': inputs, 'img_photo': targets}
        data_batch_cuda = copy.deepcopy(data_batch)
        data_batch_cuda['img_mask'] = inputs.cuda()
        data_batch_cuda['img_photo'] = targets.cuda()

        # forward_test
        with torch.no_grad():
            outputs = synthesizer(
                data_batch_cuda['img_mask'],
                target_domain='photo',
                test_mode=True)
        assert torch.equal(outputs['source'],
                           data_batch_cuda['img_mask'].cpu())
        assert torch.is_tensor(outputs['target'])
        assert outputs['target'].size() == (1, 3, 64, 64)

        with torch.no_grad():
            outputs = synthesizer(
                data_batch_cuda['img_photo'],
                target_domain='mask',
                test_mode=True)
        assert torch.equal(outputs['source'],
                           data_batch_cuda['img_photo'].cpu())
        assert torch.is_tensor(outputs['target'])
        assert outputs['target'].size() == (1, 3, 64, 64)

        # test forward_train
        with torch.no_grad():
            outputs = synthesizer(
                data_batch_cuda['img_mask'],
                target_domain='photo',
                test_mode=False)
        assert torch.equal(outputs['source'], data_batch_cuda['img_mask'])
        assert torch.is_tensor(outputs['target'])
        assert outputs['target'].size() == (1, 3, 64, 64)

        with torch.no_grad():
            outputs = synthesizer(
                data_batch_cuda['img_photo'],
                target_domain='mask',
                test_mode=False)
        assert torch.equal(outputs['source'], data_batch_cuda['img_photo'])
        assert torch.is_tensor(outputs['target'])
        assert outputs['target'].size() == (1, 3, 64, 64)

        # train_step
        inputs = torch.rand(3, 64, 64).cuda()
        targets = torch.rand(3, 64, 64).cuda()
        data_batch_cuda = [
            dict(inputs={
                'img_mask': inputs,
                'img_photo': targets
            })
        ]
        log_vars = synthesizer.train_step(data_batch_cuda, optimizer)
        assert isinstance(log_vars, dict)
        for v in [
                'loss_gan_d_mask', 'loss_gan_d_photo', 'loss_gan_g_mask',
                'loss_gan_g_photo', 'cycle_loss', 'id_loss'
        ]:
            assert isinstance(log_vars[v].item(), float)

    # test disc_steps and disc_init_steps
    train_settings = dict(discriminator_steps=2, disc_init_steps=2)
    synthesizer = CycleGAN(
        **model_cfg, **train_settings, data_preprocessor=GANDataPreprocessor())
    optimizer = OptimWrapperDict(
        generators=OptimWrapper(
            obj_from_dict(
                optim_cfg, torch.optim,
                dict(params=getattr(synthesizer, 'generators').parameters()))),
        discriminators=OptimWrapper(
            obj_from_dict(
                optim_cfg, torch.optim,
                dict(
                    params=getattr(synthesizer,
                                   'discriminators').parameters()))))

    inputs = torch.rand(3, 64, 64)
    targets = torch.rand(3, 64, 64)
    data_batch = [dict(inputs={'img_mask': inputs, 'img_photo': targets})]
    # iter 0, 1
    for i in range(2):
        message_hub.update_info('iter', i)
        log_vars = synthesizer.train_step(data_batch, optimizer)
        assert isinstance(log_vars, dict)
        for v in [
                'loss_gan_g_mask', 'loss_gan_g_photo', 'cycle_loss', 'id_loss'
        ]:
            assert log_vars.get(v) is None
        assert isinstance(log_vars['loss_gan_d_mask'].item(), float)
        assert isinstance(log_vars['loss_gan_d_photo'].item(), float)

    # iter 2, 3, 4, 5
    for i in range(2, 6):
        message_hub.update_info('iter', i)
        log_vars = synthesizer.train_step(data_batch, optimizer)
        print(log_vars.keys())
        assert isinstance(log_vars, dict)
        log_check_list = [
            'loss_gan_d_mask', 'loss_gan_d_photo', 'loss_gan_g_mask',
            'loss_gan_g_photo', 'cycle_loss', 'id_loss'
        ]
        if (i + 1) % 2 == 1:
            log_None_list = [
                'loss_gan_g_mask', 'loss_gan_g_photo', 'cycle_loss', 'id_loss'
            ]
            for v in log_None_list:
                assert log_vars.get(v) is None
                log_check_list.remove(v)
        for v in log_check_list:
            assert isinstance(log_vars[v].item(), float)

    # test GAN image buffer size = 0
    inputs = torch.rand(1, 3, 64, 64)
    targets = torch.rand(1, 3, 64, 64)
    data_batch = {'img_mask': inputs, 'img_photo': targets}
    train_settings = dict(buffer_size=0)
    synthesizer = CycleGAN(
        **model_cfg, **train_settings, data_preprocessor=GANDataPreprocessor())
    optimizer = OptimWrapperDict(
        generators=OptimWrapper(
            obj_from_dict(
                optim_cfg, torch.optim,
                dict(params=getattr(synthesizer, 'generators').parameters()))),
        discriminators=OptimWrapper(
            obj_from_dict(
                optim_cfg, torch.optim,
                dict(
                    params=getattr(synthesizer,
                                   'discriminators').parameters()))))
    log_vars = synthesizer.train_step(data_batch, optimizer)
    assert isinstance(log_vars, dict)
    for v in [
            'loss_gan_d_mask', 'loss_gan_d_photo', 'loss_gan_g_mask',
            'loss_gan_g_photo', 'cycle_loss', 'id_loss'
    ]:
        assert isinstance(log_vars[v].item(), float)
