_base_ = [
    '../_base_/models/lsgan/lsgan_128x128.py',
    '../_base_/datasets/unconditional_imgs_128x128.py',
    '../_base_/default_runtime.py'
]

total_iters = 160000
disc_step = 1
train_cfg = dict(max_iters=total_iters * disc_step)

# define dataset
batch_size = 64
data_root = './data/lsun/bedroom_train'

train_dataloader = dict(
    batch_size=batch_size, dataset=dict(data_root=data_root))

val_dataloader = dict(batch_size=batch_size, dataset=dict(data_root=data_root))

test_dataloader = dict(
    batch_size=batch_size, dataset=dict(data_root=data_root))

optim_wrapper = dict(
    generator=dict(optimizer=dict(type='Adam', lr=0.0001, betas=(0.5, 0.99))),
    discriminator=dict(
        optimizer=dict(type='Adam', lr=0.0001, betas=(0.5, 0.99))))

# adjust running config
# METRICS
metrics = [
    dict(
        type='FrechetInceptionDistance',
        prefix='FID-Full-50k',
        fake_nums=50000,
        inception_style='StyleGAN',
        sample_model='orig')
]
val_evaluator = dict(metrics=metrics)
test_evaluator = dict(metrics=metrics)
