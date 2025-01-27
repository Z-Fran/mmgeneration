_base_ = ['./wgangp_GN_celeba-cropped_128_b64x1_160kiter.py']

loss_config = dict(gp_norm_mode='HWC', gp_loss_weight=50)
model = dict(loss_config=loss_config)

batch_size = 64
data_root = './data/lsun/bedroom_train'
train_dataloader = dict(
    batch_size=batch_size, dataset=dict(data_root=data_root))

val_dataloader = dict(batch_size=batch_size, dataset=dict(data_root=data_root))

test_dataloader = dict(
    batch_size=batch_size, dataset=dict(data_root=data_root))
