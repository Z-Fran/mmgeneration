_base_ = [
    '../_base_/models/stylegan/stylegan3_base.py',
    '../_base_/default_runtime.py', '../_base_/datasets/ffhq_flip.py'
]

synthesis_cfg = {
    'type': 'SynthesisNetwork',
    'channel_base': 32768,
    'channel_max': 512,
    'magnitude_ema_beta': 0.999
}

model = dict(
    generator=dict(
        out_size=1024,
        img_channels=3,
        synthesis_cfg=synthesis_cfg,
        rgb2bgr=True),
    discriminator=dict(in_size=1024))

batch_size = 4
data_root = './data/ffhq/images'

train_dataloader = dict(
    batch_size=batch_size, dataset=dict(data_root=data_root))

val_dataloader = dict(batch_size=batch_size, dataset=dict(data_root=data_root))

test_dataloader = dict(
    batch_size=batch_size, dataset=dict(data_root=data_root))

train_cfg = train_dataloader = optim_wrapper = None

metrics = [
    dict(
        type='FrechetInceptionDistance',
        prefix='FID-Full-50k',
        fake_nums=50000,
        inception_style='StyleGAN',
        sample_model='ema')
]
val_evaluator = dict(metrics=metrics)
test_evaluator = dict(metrics=metrics)
