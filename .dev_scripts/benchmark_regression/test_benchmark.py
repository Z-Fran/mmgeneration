import argparse
import os
import os.path as osp
import pickle
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from modelindex.load_model_index import load
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

console = Console()
MMGEN_ROOT = Path(__file__).absolute().parents[2]

# key-in-metafile: key-in-results.pkl
METRICS_MAP = {
    'SWD': {
        'keys': ['SWD/avg'],
        'tolerance': 0.1,
        'rule': 'less'
    },
    'MS-SSIM': {
        'keys': ['MS-SSIM'],
        'tolerance': 0.1,
        'rule': 'larger'
    },
    'FID': {
        'keys': ['FID-Full-50k/fid'],
        'tolerance': 0.1,
        'rule': 'less'
    },
    'FID50k': {
        'keys': ['FID-Full-50k/fid'],
        'tolerance': 0.1,
        'rule': 'less'
    },
    'IS': {
        'keys': ['IS-50k/is'],
        'tolerance': 0.1,
        'rule': 'larger'
    },
    'IS50k': {
        'keys': ['IS-50k/is'],
        'tolerance': 0.1,
        'rule': 'larger'
    },
    'Precision50k': {
        'keys': ['PR-50K/precision'],
        'tolerance': 0.1,
        'rule': 'large'
    },
    'Recall50k': {
        'keys': ['PR-50K/recall'],
        'tolerance': 0.1,
        'rule': 'large'
    },
    'Precision10k': {
        'keys': ['PR-10K/precision'],
        'tolerance': 0.1,
        'rule': 'large'
    },
    'Recall10k': {
        'keys': ['PR-10K/recall'],
        'tolerance': 0.1,
        'rule': 'large'
    },
    # 'PPL': {},  # TODO: no ppl in metafiles?
    'EQ-R': {
        'keys': ['EQ/eqr'],
        'tolerance': 0.1,
        'rule': 'larger'
    },
    'EQ-T': {
        'keys': ['EQ/eqt_int'],
        'tolerance': 0.1,
        'rule': 'larger'
    },
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test all models' accuracy in model-index.yml")
    parser.add_argument(
        'partition', type=str, help='Cluster partition to use.')
    parser.add_argument('checkpoint_root', help='Checkpoint file root path.')
    parser.add_argument(
        '--job-name',
        type=str,
        default='gen-test-benchmark',
        help='Slurm job name prefix')
    parser.add_argument('--port', type=int, default=29666, help='dist port')
    parser.add_argument(
        '--use-ceph-config',
        action='store_true',
        default=False,
        help='Use ceph configs or not.')
    parser.add_argument(
        '--models', nargs='+', type=str, help='Specify model names to run.')
    parser.add_argument(
        '--work-dir',
        default='work_dirs/benchmark_test',
        help='the dir to save metric')
    parser.add_argument(
        '--run', action='store_true', help='run script directly')
    parser.add_argument(
        '--local',
        action='store_true',
        help='run at local instead of cluster.')
    parser.add_argument(
        '--mail', type=str, help='Mail address to watch test status.')
    parser.add_argument(
        '--mail-type',
        nargs='+',
        default=['BEGIN'],
        choices=['NONE', 'BEGIN', 'END', 'FAIL', 'REQUEUE', 'ALL'],
        help='Mail address to watch test status.')
    parser.add_argument(
        '--quotatype',
        default=None,
        choices=['reserved', 'auto', 'spot'],
        help='Quota type, only available for phoenix-slurm>=0.2')
    parser.add_argument(
        '--summary',
        action='store_true',
        help='Summarize benchmark test results.')
    parser.add_argument('--save', action='store_true', help='Save the summary')

    args = parser.parse_args()
    return args


def create_test_job_batch(commands, model_info, args, port, script_name):
    config_http_prefix_blob = ('https://github.com/open-mmlab/mmgeneration/'
                               'blob/master/')
    config_http_prefix_tree = ('https://github.com/open-mmlab/mmgeneration/'
                               'tree/master/')
    fname = model_info.name

    config = model_info.config
    if config.startswith('http'):
        config = config.replace(config_http_prefix_blob, './')
        config = config.replace(config_http_prefix_tree, './')
    if args.use_ceph_config:
        config = config.replace('configs', 'configs_ceph')

    config = Path(config)
    assert config.exists(), f'{fname}: {config} not found.'

    http_prefix = 'https://download.openmmlab.com/mmgen/'
    if 's3://' in args.checkpoint_root:
        from mmcv.fileio import FileClient
        from petrel_client.common.exception import AccessDeniedError
        file_client = FileClient.infer_client(uri=args.checkpoint_root)
        checkpoint = file_client.join_path(
            args.checkpoint_root, model_info.weights[len(http_prefix):])
        try:
            exists = file_client.exists(checkpoint)
        except AccessDeniedError:
            exists = False
    else:
        checkpoint_root = Path(args.checkpoint_root)
        checkpoint = checkpoint_root / model_info.weights[len(http_prefix):]
        exists = checkpoint.exists()
    if not exists:
        print(f'WARNING: {fname}: {checkpoint} not found.')
        return None

    job_name = f'{args.job_name}_{fname}'
    work_dir = Path(args.work_dir) / fname
    work_dir.mkdir(parents=True, exist_ok=True)
    result_file = work_dir / 'result.pkl'

    if args.mail is not None and 'NONE' not in args.mail_type:
        mail_cfg = (f'#SBATCH --mail {args.mail}\n'
                    f'#SBATCH --mail-type {args.mail_type}\n')
    else:
        mail_cfg = ''

    if args.quotatype is not None:
        quota_cfg = f'#SBATCH --quotatype {args.quotatype}\n'
    else:
        quota_cfg = ''

    launcher = 'none' if args.local else 'slurm'
    runner = 'python' if args.local else 'srun python'

    job_script = (f'#!/bin/bash\n'
                  f'#SBATCH --output {work_dir}/job.%j.out\n'
                  f'#SBATCH --partition={args.partition}\n'
                  f'#SBATCH --job-name {job_name}\n'
                  f'#SBATCH --gres=gpu:8\n'
                  f'{mail_cfg}{quota_cfg}'
                  f'#SBATCH --ntasks-per-node=8\n'
                  f'#SBATCH --ntasks=8\n'
                  f'#SBATCH --cpus-per-task=5\n\n'
                  f'export MASTER_PORT={port}\n'
                  f'{runner} -u {script_name} {config} {checkpoint} '
                  f'--work-dir={work_dir} '
                  f'--out={result_file} '
                  f'--launcher={launcher}\n')

    with open(work_dir / 'job.sh', 'w') as f:
        f.write(job_script)

    commands.append(f'echo "{config}"')
    if args.local:
        commands.append(f'bash {work_dir}/job.sh')
    else:
        commands.append(f'sbatch {work_dir}/job.sh')

    return work_dir / 'job.sh'


def test(args):
    # parse model-index.yml
    model_index_file = MMGEN_ROOT / 'model-index.yml'
    model_index = load(str(model_index_file))
    model_index.build_models_with_collections()
    models = OrderedDict({model.name: model for model in model_index.models})

    script_name = osp.join('tools', 'test.py')
    port = args.port

    commands = []
    if args.models:
        patterns = [re.compile(pattern) for pattern in args.models]
        filter_models = {}
        for k, v in models.items():
            if any([re.match(pattern, k) for pattern in patterns]):
                filter_models[k] = v
        if len(filter_models) == 0:
            print('No model found, please specify models in:')
            print('\n'.join(models.keys()))
            return
        models = filter_models

    preview_script = ''
    for model_info in models.values():

        if model_info.results is None:
            continue

        script_path = create_test_job_batch(commands, model_info, args, port,
                                            script_name)
        preview_script = script_path or preview_script
        port += 1

    command_str = '\n'.join(commands)

    preview = Table()
    preview.add_column(str(preview_script))
    preview.add_column('Shell command preview')
    preview.add_row(
        Syntax.from_path(
            preview_script,
            background_color='default',
            line_numbers=True,
            word_wrap=True),
        Syntax(
            command_str,
            'bash',
            background_color='default',
            line_numbers=True,
            word_wrap=True))
    console.print(preview)

    if args.run:
        os.system(command_str)
    else:
        console.print('Please set "--run" to start the job')


def show_summary(summary_data, models_map, work_dir, save=False):
    table = Table(title='Test Benchmark Regression Summary')
    table.add_column('Model')
    md_header = ['Model']
    for metric in METRICS_MAP:
        table.add_column(f'{metric} (expect)')
        table.add_column(f'{metric}')
        md_header.append(f'{metric} (expect)')
        md_header.append(f'{metric}')
    table.add_column('Date')
    md_header.append('Config')

    def set_color(value, expect, tolerance, rule):
        if value > expect + tolerance:
            return 'green' if rule == 'larger' else 'red'
        elif value < expect - tolerance:
            return 'red' if rule == 'larger' else 'green'
        else:
            return 'white'

    md_rows = ['| ' + ' | '.join(md_header) + ' |\n']
    md_rows.append('|:' + ':|:'.join(['---'] * len(md_header)) + ':|\n')

    for model_name, summary in summary_data.items():
        row = [model_name]
        md_row = [model_name]
        for metric_key in METRICS_MAP:
            if metric_key in summary:
                metric = summary[metric_key]
                expect = round(metric['expect'], 2)
                result = round(metric['result'], 2)
                tolerance = metric['tolerance']
                rule = metric['rule']
                color = set_color(result, expect, tolerance, rule)
                row.append(f'{expect:.2f}')
                row.append(f'[{color}]{result:.2f}[/{color}]')
                md_row.append(f'{expect:.2f}')
                md_row.append(f'{result:.2f}')
            else:
                row.extend([''] * 2)
                md_row.extend([''] * 2)
        if 'date' in summary:
            row.append(summary['date'])
            md_row.append(summary['date'])
        else:
            row.append('')
            md_row.append('')
        table.add_row(*row)

        # add config to row
        model_info = models_map[model_name]
        md_row.append(model_info.config)
        md_rows.append('| ' + ' | '.join(md_row) + ' |\n')

    console.print(table)

    if save:
        summary_path = work_dir / 'test_benchmark_summary.md'
        with open(summary_path, 'w') as file:
            file.write('# Test Benchmark Regression Summary\n')
            file.writelines(md_rows)


def summary(args):
    model_index_file = MMGEN_ROOT / 'model-index.yml'
    model_index = load(str(model_index_file))
    model_index.build_models_with_collections()
    models = OrderedDict({model.name: model for model in model_index.models})

    work_dir = Path(args.work_dir)

    if args.models:
        patterns = [re.compile(pattern) for pattern in args.models]
        filter_models = {}
        for k, v in models.items():
            if any([re.match(pattern, k) for pattern in patterns]):
                filter_models[k] = v
        if len(filter_models) == 0:
            print('No model found, please specify models in:')
            print('\n'.join(models.keys()))
            return
        models = filter_models

    summary_data = {}
    for model_name, model_info in models.items():

        if model_info.results is None:
            continue

        # Skip if not found result file.
        result_file = work_dir / model_name / 'result.pkl'
        if not result_file.exists():
            summary_data[model_name] = {}
            continue

        with open(result_file, 'rb') as file:
            results = pickle.load(file)
        date = datetime.fromtimestamp(result_file.lstat().st_mtime)

        expect_metrics = model_info.results[0].metrics

        # extract metrics
        summary = {'date': date.strftime('%Y-%m-%d')}
        for key_yml, key_tolerance in METRICS_MAP.items():
            key_results = key_tolerance['keys']
            tolerance = key_tolerance['tolerance']
            rule = key_tolerance['rule']

            for key_result in key_results:
                if key_yml in expect_metrics and key_result in results:
                    expect_result = float(expect_metrics[key_yml])
                    result = float(results[key_result])
                    summary[key_yml] = dict(
                        expect=expect_result,
                        result=result,
                        tolerance=tolerance,
                        rule=rule)

        summary_data[model_name] = summary

    show_summary(summary_data, models, work_dir, args.save)


def main():
    args = parse_args()

    if args.summary:
        summary(args)
    else:
        test(args)


if __name__ == '__main__':
    main()
