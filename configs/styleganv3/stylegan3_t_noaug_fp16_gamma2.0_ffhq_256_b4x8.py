_base_ = [
    '../_base_/models/stylegan/stylegan3_base.py',
    '../_base_/datasets/unconditional_imgs_flip_lanczos_resize_256x256.py',
    '../_base_/default_runtime.py'
]

synthesis_cfg = {
    'type': 'SynthesisNetwork',
    'channel_base': 16384,
    'channel_max': 512,
    'magnitude_ema_beta': 0.999
}
r1_gamma = 2.  # set by user
d_reg_interval = 16

ema_config = dict(
    type='RampUpEMA',
    interval=1,
    ema_kimg=10,
    ema_rampup=0.05,
    batch_size=32,
    eps=1e-8,
    start_iter=0)

model = dict(
    generator=dict(out_size=256, img_channels=3, synthesis_cfg=synthesis_cfg),
    discriminator=dict(in_size=256, channel_multiplier=1),
    loss_config=dict(r1_loss_weight=r1_gamma / 2.0 * d_reg_interval),
    ema_config=ema_config)

batch_size = 4
data_root = 'data/ffhq/images'

train_dataloader = dict(
    batch_size=batch_size, dataset=dict(data_root=data_root))

val_dataloader = dict(batch_size=batch_size, dataset=dict(data_root=data_root))

test_dataloader = dict(
    batch_size=batch_size, dataset=dict(data_root=data_root))

train_cfg = dict(max_iters=800002)

# VIS_HOOK
custom_hooks = [
    dict(
        type='GenVisualizationHook',
        interval=5000,
        fixed_input=True,
        vis_kwargs_list=dict(type='GAN', name='fake_img'))
]

# METRICS
metrics = [
    dict(
        type='FrechetInceptionDistance',
        prefix='FID-Full-50k',
        fake_nums=50000,
        inception_style='StyleGAN',
        sample_model='ema'),
    dict(
        type='Equivariance',
        fake_nums=50000,
        sample_mode='ema',
        prefix='EQ',
        eq_cfg=dict(
            compute_eqt_int=True, compute_eqt_frac=True, compute_eqr=True))
]

val_evaluator = dict(metrics=metrics)
test_evaluator = dict(metrics=metrics)
