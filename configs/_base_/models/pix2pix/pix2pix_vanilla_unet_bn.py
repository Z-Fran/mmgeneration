source_domain = None  # set by user
target_domain = None  # set by user
# model settings
model = dict(
    type='Pix2Pix',
    data_preprocessor=dict(type='GANDataPreprocessor'),
    generator=dict(
        type='UnetGenerator',
        in_channels=3,
        out_channels=3,
        num_down=8,
        base_channels=64,
        norm_cfg=dict(type='BN'),
        use_dropout=True,
        init_cfg=dict(type='normal', gain=0.02)),
    discriminator=dict(
        type='PatchDiscriminator',
        in_channels=6,
        base_channels=64,
        num_conv=3,
        norm_cfg=dict(type='BN'),
        init_cfg=dict(type='normal', gain=0.02)),
    default_domain=target_domain,
    reachable_domains=[target_domain],
    related_domains=[target_domain, source_domain])
