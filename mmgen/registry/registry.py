# Copyright (c) OpenMMLab. All rights reserved.
"""MMGeneration provides 14 registry nodes to support using modules across
projects. Each node is a child of the root registry in MMEngine.

More details can be found at
https://mmengine.readthedocs.io/en/latest/tutorials/registry.html.
"""

from mmengine.registry import DATA_SAMPLERS as MMENGINE_DATA_SAMPLERS
from mmengine.registry import DATASETS as MMENGINE_DATASETS
from mmengine.registry import EVALUATOR as MMENGINE_EVALUATOR
from mmengine.registry import HOOKS as MMENGINE_HOOKS
from mmengine.registry import LOOPS as MMENGINE_LOOPS
from mmengine.registry import METRICS as MMENGINE_METRICS
from mmengine.registry import MODEL_WRAPPERS as MMENGINE_MODEL_WRAPPERS
from mmengine.registry import MODELS as MMENGINE_MODELS
from mmengine.registry import \
    OPTIM_WRAPPER_CONSTRUCTORS as MMENGINE_OPTIM_WRAPPER_CONSTRUCTORS
from mmengine.registry import OPTIMIZERS as MMENGINE_OPTIMIZERS
from mmengine.registry import PARAM_SCHEDULERS as MMENGINE_PARAM_SCHEDULERS
from mmengine.registry import TRANSFORMS as MMENGINE_TRANSFORMS
from mmengine.registry import VISBACKENDS as MMENGINE_VISBACKENDS
from mmengine.registry import VISUALIZERS as MMENGINE_VISUALIZERS
from mmengine.registry import Registry

# manage all kinds of metrics
METRICS = Registry('metric', parent=MMENGINE_METRICS)
# manage all kinds of loops like `DynamicIterBasedTrainLoop`
LOOPS = Registry('loop', parent=MMENGINE_LOOPS)
# manage data-related modules
DATASETS = Registry('dataset', parent=MMENGINE_DATASETS)
DATA_SAMPLERS = Registry('data sampler', parent=MMENGINE_DATA_SAMPLERS)
TRANSFORMS = Registry('transform', parent=MMENGINE_TRANSFORMS)

# mangage all kinds of modules inheriting `nn.Module`
MODELS = Registry('model', parent=MMENGINE_MODELS)
MODULES = Registry('module')

# manage all kinds of hooks like `CheckpointHook`
HOOKS = Registry('hook', parent=MMENGINE_HOOKS)

# mangage all kinds of model wrappers like 'MMDistributedDataParallel'
MODEL_WRAPPERS = Registry('model_wrapper', parent=MMENGINE_MODEL_WRAPPERS)

# mangage all kinds of optimizers like `SGD` and `Adam`
OPTIMIZERS = Registry('optimizer', parent=MMENGINE_OPTIMIZERS)
# manage constructors that customize the optimization hyperparameters.
OPTIM_WRAPPER_CONSTRUCTORS = Registry(
    'optimizer constructor', parent=MMENGINE_OPTIM_WRAPPER_CONSTRUCTORS)
# mangage all kinds of parameter schedulers like `MultiStepLR`
PARAM_SCHEDULERS = Registry(
    'parameter scheduler', parent=MMENGINE_PARAM_SCHEDULERS)

# manage visualizer
VISUALIZERS = Registry('visualizer', parent=MMENGINE_VISUALIZERS)
# manage visualizer backend
VISBACKENDS = Registry('vis_backend', parent=MMENGINE_VISBACKENDS)

# manage evaluator
EVALUATOR = Registry('evaluator', parent=MMENGINE_EVALUATOR)
