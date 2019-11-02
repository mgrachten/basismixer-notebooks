import json
import logging
import os

import numpy as np
import torch
from torch.utils.data import DataLoader, ConcatDataset
# from torch.utils.data.sampler import SubsetRandomSampler

from basismixer.predictive_models import (construct_model as c_model,
                                          SupervisedTrainer,
                                          MSELoss)
from basismixer.utils import load_pyc_bz, save_pyc_bz

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

RNG = np.random.RandomState(1984)

def construct_dataloaders(dataset_fn, batch_size=10,
                          valid_size=0.2):
    """
    Load a dataset and prepare DataLoaders for training and
    validation.
    """
    # load dataset
    data = load_pyc_bz(dataset_fn)
    # Dataset
    dataset = data['dataset']
    # Input names (basis functions)
    in_names = data['in_names']
    # Output names (expressive parameters)
    out_names = data['out_names']
    
    # Split dataset in training and validation
    dataset_idx = np.arange(len(dataset))
    RNG.shuffle(dataset_idx)
    len_valid = int(np.round(len(dataset) * valid_size))
    valid_idx = dataset_idx[0:len_valid]
    train_idx = dataset_idx[len_valid:]
    
    # Subset of the dataset for training
    train_sampler = SubsetRandomSampler(train_idx)
    # Subset of the dataset for validation
    valid_sampler = SubsetRandomSampler(valid_idx)
    LOGGER.info('Using {0} instances for')
    train_dataloader = DataLoader(dataset,
                                  batch_size=batch_size,
                                  # shuffle=True,
                                  sampler=train_sampler)
    valid_dataloader = DataLoader(dataset,
                                  batch_size=batch_size,
                                  sampler=valid_sampler)
    
    return dataset, train_dataloader, valid_dataloader

def construct_model(config, in_names, out_names, out_dir):
    model_cfg = config['model'].copy()
    model_cfg['args']['input_names'] = in_names
    model_cfg['args']['input_size'] = len(in_names)
    model_cfg['args']['output_names'] = out_names
    model_cfg['args']['output_size'] = len(out_names)
    model_name = ('-'.join(out_names) +
                  '-' + ('onsetwise' if config['onsetwise'] else 'notewise'))
    model_out_dir = os.path.join(out_dir, model_name)
    if not os.path.exists(model_out_dir):
        os.mkdir(model_out_dir)
    # save model config for later saving model
    config_out = os.path.join(model_out_dir, 'config.json')
    LOGGER.info('Saving config in {0}'.format(config_out))
    json.dump(jsonize_dict(model_cfg),
              open(config_out, 'w'),
              indent=2)
    model = c_model(model_cfg)

    return model, model_out_dir

def setup_output_directory(out_dir='/tmp/trained_models'):
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)
    return out_dir

def jsonize_dict(input_dict):
    out_dict = dict()
    for k, v in input_dict.items():
        if isinstance(v, np.ndarray):
            out_dict[k] = v.tolist()
        elif isinstance(v, dict):
            out_dict[k] = jsonize_dict(v)
        else:
            out_dict[k] = v
    return out_dict

def split_dataset(dataset, test_size=0.2, valid_size=0.2):

    n_pieces = len(dataset.datasets)

    dataset_idx = np.arange(n_pieces)
    RNG.shuffle(dataset_idx)
    len_test = int(n_pieces * test_size)
    len_valid = np.maximum(int((n_pieces - len_test) * valid_size), 1)

    test_idxs = dataset_idx[:len_test]
    valid_idxs = dataset_idx[len_test:len_test + len_valid]
    train_idxs = dataset_idx[len_test + len_valid:]

    print('Pieces per dataset\n' +
          'Train set:\t{0}\n'.format(len(train_idxs)) +
          'Test set:\t{0}\n'.format(len(test_idxs)) +
          'Validation set:\t{0}\n'.format(len(valid_idxs)))

    train_set = ConcatDataset([dataset.datasets[i] for i in train_idxs])
    print(train_idxs)
    valid_set = ConcatDataset([dataset.datasets[i] for i in valid_idxs])
    print(valid_idxs)
    test_set = ConcatDataset([dataset.datasets[i] for i in test_idxs])
    print(test_idxs)
    print(len(train_set), len(valid_set), len(test_set))

    return train_set, valid_set, test_set



def train_model(model, train_set, valid_set,
                config, out_dir):
    batch_size = config['train_args'].pop('batch_size')

    #### Create train and validation data loaders #####
    train_loader = DataLoader(train_set,
                              batch_size=batch_size,
                              shuffle=True)
    valid_loader = DataLoader(valid_set,
                              batch_size=batch_size,
                              shuffle=False)

    loss = MSELoss()

    ### Construct the optimizer ####
    optim_name, optim_args = config['train_args']['optimizer']
    optim = getattr(torch.optim, optim_name)
    config['train_args']['optimizer'] = optim(model.parameters(), **optim_args)

    trainer = SupervisedTrainer(model=model,
                                train_loss=loss,
                                valid_loss=loss,
                                train_dataloader=train_loader,
                                valid_dataloader=valid_loader,
                                out_dir=out_dir,
                                **config['train_args'])
    trainer.train()
