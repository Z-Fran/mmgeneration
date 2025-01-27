# Copyright (c) OpenMMLab. All rights reserved.
import torch
import torch.nn.functional as F
from mmengine import MessageHub

from mmgen.core.data_structures.gen_data_sample import GenDataSample
from mmgen.core.data_structures.pixel_data import PixelData
from mmgen.registry import MODELS
from mmgen.typing import ForwardOutputs, ValTestStepInputs
from ..common import set_requires_grad
from .static_translation_gan import StaticTranslationGAN


@MODELS.register_module()
class Pix2Pix(StaticTranslationGAN):
    """Pix2Pix model for paired image-to-image translation.

    Ref:
     Image-to-Image Translation with Conditional Adversarial Networks
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def forward_test(self, img, target_domain, **kwargs):
        """Forward function for testing.

        Args:
            img (tensor): Input image tensor.
            target_domain (str): Target domain of output image.
            kwargs (dict): Other arguments.

        Returns:
            dict: Forward results.
        """
        # This is a trick for Pix2Pix
        # ref: https://github.com/junyanz/pytorch-CycleGAN-and-pix2pix/blob/e1bdf46198662b0f4d0b318e24568205ec4d7aee/test.py#L54  # noqa
        self.train()
        target = self.translation(img, target_domain=target_domain, **kwargs)
        results = dict(source=img.cpu(), target=target.cpu())
        return results

    def _get_disc_loss(self, outputs):
        # GAN loss for the discriminator
        losses = dict()

        discriminators = self.get_module(self.discriminators)
        target_domain = self._default_domain
        source_domain = self.get_other_domains(target_domain)[0]
        fake_ab = torch.cat((outputs[f'real_{source_domain}'],
                             outputs[f'fake_{target_domain}']), 1)
        fake_pred = discriminators[target_domain](fake_ab.detach())
        losses['loss_gan_d_fake'] = F.binary_cross_entropy_with_logits(
            fake_pred, 0. * torch.ones_like(fake_pred))
        real_ab = torch.cat((outputs[f'real_{source_domain}'],
                             outputs[f'real_{target_domain}']), 1)
        real_pred = discriminators[target_domain](real_ab)
        losses['loss_gan_d_real'] = F.binary_cross_entropy_with_logits(
            real_pred, 1. * torch.ones_like(real_pred))

        loss_d, log_vars_d = self.parse_losses(losses)
        loss_d *= 0.5

        return loss_d, log_vars_d

    def _get_gen_loss(self, outputs):
        target_domain = self._default_domain
        source_domain = self.get_other_domains(target_domain)[0]
        losses = dict()

        discriminators = self.get_module(self.discriminators)
        # GAN loss for the generator
        fake_ab = torch.cat((outputs[f'real_{source_domain}'],
                             outputs[f'fake_{target_domain}']), 1)
        fake_pred = discriminators[target_domain](fake_ab)
        losses['loss_gan_g'] = F.binary_cross_entropy_with_logits(
            fake_pred, 1. * torch.ones_like(fake_pred))

        loss_g, log_vars_g = self.parse_losses(losses)
        return loss_g, log_vars_g

    def train_step(self, data, optim_wrapper=None):
        """Training step function.

        Args:
            data_batch (dict): Dict of the input data batch.
            optimizer (dict[torch.optim.Optimizer]): Dict of optimizers for
                the generator and discriminator.
            ddp_reducer (:obj:`Reducer` | None, optional): Reducer from ddp.
                It is used to prepare for ``backward()`` in ddp. Defaults to
                None.
            running_status (dict | None, optional): Contains necessary basic
                information for training, e.g., iteration number. Defaults to
                None.

        Returns:
            dict: Dict of loss, information for logger, the number of samples\
                and results for visualization.
        """
        message_hub = MessageHub.get_current_instance()
        curr_iter = message_hub.get_info('iter')
        inputs_dict, data_sample = self.data_preprocessor(data, True)

        disc_optimizer_wrapper = optim_wrapper['discriminators']
        disc_accu_iters = disc_optimizer_wrapper._accumulative_counts

        target_domain = self._default_domain
        source_domain = self.get_other_domains(self._default_domain)[0]
        source_image = inputs_dict[f'img_{source_domain}']
        target_image = inputs_dict[f'img_{target_domain}']

        # forward generator
        outputs = dict()
        results = self(
            source_image, target_domain=self._default_domain, test_mode=False)
        outputs[f'real_{source_domain}'] = results['source']
        outputs[f'fake_{target_domain}'] = results['target']
        outputs[f'real_{target_domain}'] = target_image
        log_vars = dict()

        # discriminator
        set_requires_grad(self.discriminators, True)
        # optimize
        disc_optimizer_wrapper.zero_grad()
        loss_d, log_vars_d = self._get_disc_loss(outputs)
        log_vars.update(log_vars_d)
        loss_d.backward()
        disc_optimizer_wrapper.step()

        # generator, no updates to discriminator parameters.
        gen_optimizer_wrapper = optim_wrapper['generators']
        if ((curr_iter + 1) % (self.discriminator_steps * disc_accu_iters) == 0
                and curr_iter >= self.disc_init_steps):
            set_requires_grad(self.discriminators, False)
            # optimize
            gen_optimizer_wrapper.zero_grad()
            loss_g, log_vars_g = self._get_gen_loss(outputs)
            log_vars.update(log_vars_g)
            loss_g.backward()
            gen_optimizer_wrapper.step()

        return log_vars

    def test_step(self, data: ValTestStepInputs) -> ForwardOutputs:
        """Gets the generated image of given data. Same as :meth:`val_step`.

        Args:
            data (ValTestStepInputs): Data sampled from metric specific
                sampler. More detials in `Metrics` and `Evaluator`.

        Returns:
            ForwardOutputs: Generated image or image dict.
        """
        inputs_dict, data_sample = self.data_preprocessor(data)
        target_domain = self._reachable_domains[0]
        source_domain = self.get_other_domains(target_domain)[0]
        outputs = self.forward_test(
            inputs_dict[f'img_{source_domain}'], target_domain=target_domain)

        batch_sample_list = []
        num_batches = next(iter(outputs.values())).shape[0]
        for idx in range(num_batches):
            gen_sample = GenDataSample()
            if data_sample:
                gen_sample.update(data_sample[idx])
            setattr(gen_sample, f'gt_{target_domain}',
                    PixelData(data=inputs_dict[f'img_{target_domain}'][idx]))
            setattr(gen_sample, f'fake_{target_domain}',
                    PixelData(data=outputs['target'][idx]))
            setattr(gen_sample, f'gt_{source_domain}',
                    PixelData(data=inputs_dict[f'img_{source_domain}'][idx]))
            batch_sample_list.append(gen_sample)
        return batch_sample_list

    def val_step(self, data: ValTestStepInputs) -> ForwardOutputs:
        """Gets the generated image of given data. Same as :meth:`val_step`.

        Args:
            data (ValTestStepInputs): Data sampled from metric specific
                sampler. More detials in `Metrics` and `Evaluator`.

        Returns:
            ForwardOutputs: Generated image or image dict.
        """
        inputs_dict, data_sample = self.data_preprocessor(data)
        target_domain = self._reachable_domains[0]
        source_domain = self.get_other_domains(target_domain)[0]
        outputs = self.forward_test(
            inputs_dict[f'img_{source_domain}'], target_domain=target_domain)

        batch_sample_list = []
        num_batches = next(iter(outputs.values())).shape[0]
        for idx in range(num_batches):
            gen_sample = GenDataSample()
            if data_sample:
                gen_sample.update(data_sample[idx])
            setattr(gen_sample, f'gt_{target_domain}',
                    inputs_dict[f'img_{target_domain}'][idx])
            setattr(gen_sample, f'fake_{target_domain}',
                    outputs[f'img_{target_domain}'][idx])
            setattr(gen_sample, f'gt_{source_domain}',
                    inputs_dict[f'img_{source_domain}'][idx])
            batch_sample_list.append(gen_sample)
        return batch_sample_list
        return outputs
