import json
import logging
import os

import numpy as np
import torch
from torch.utils.data import DataLoader
from torch.utils.data.sampler import SubsetRandomSampler

from basismixer.predictive_models import (construct_model,
                                          RecurrentModel,
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


def train_model(model, config, train_loader, val_loader, out_dir):
    # Get the configuration for the trainer
    t_config = config['train_args']

    # Name of the model
    model_name = '-'.join(model.output_names) + '-' + model.input_type
    # Create a directory for storing the model parameters
    model_out_dir = os.path.join(out_dir, model_name)
    if not os.path.exists(model_out_dir):
        os.mkdir(model_out_dir)
    # Loss function
    loss = MSELoss()
    # Initialize the optimizer
    optimizer = torch.optim.Adam(model.parameters(), lr=t_config.pop('lr'))
    # Create trainer for training model in a supervised way
    trainer = SupervisedTrainer(model=model,
                                train_loss=loss,
                                optimizer=optimizer,
                                valid_loss=loss,
                                train_dataloader=train_loader,
                                valid_dataloader=val_loader,
                                out_dir=model_out_dir,
                                **t_config)
    # train the mode
    trainer.train()
