from typing import Tuple, Union, Dict

import torch
import numpy as np
import os
from basicts.runners import SimpleTimeSeriesForecastingRunner
from basicts.utils import time_features


class SumbaRunner(SimpleTimeSeriesForecastingRunner):
    def __init__(self, cfg: dict):
        super().__init__(cfg)
        # os.environ["WANDB_API_KEY"]=" "
        # wandb.init(
        #     # set the wandb project where this run will be logged
        #     project = " ",
        #     name = " ",
        #     # track hyperparameters and run metadata
        # )

        # wandb.watch(self.model, log="all")
        # self.wdb = wandb
   
    def forward(self, data: Dict, epoch: int = None, iter_num: int = None, train: bool = True, **kwargs) -> Dict:
        """
        Performs the forward pass for training, validation, and testing. 

        Args:
            data (Dict): A dictionary containing 'target' (future data) and 'inputs' (history data) (normalized by self.scaler).
            epoch (int, optional): Current epoch number. Defaults to None.
            iter_num (int, optional): Current iteration number. Defaults to None.
            train (bool, optional): Indicates whether the forward pass is for training. Defaults to True.

        Returns:
            Dict: A dictionary containing the keys:
                  - 'inputs': Selected input features.
                  - 'prediction': Model predictions.
                  - 'target': Selected target features.

        Raises:
            AssertionError: If the shape of the model output does not match [B, L, N].
        """

        future_t_index, history_t_index = data['target_t_index'], data['inputs_t_index']
        data = self.preprocessing(data)

        # Preprocess input data
        future_data, history_data = data['target'], data['inputs']
        history_data = self.to_running_device(history_data)  # Shape: [B, L, N, C]
        future_data = self.to_running_device(future_data)    # Shape: [B, L, N, C]
        history_t_index = self.to_running_device(history_t_index)  # Shape: [B, L, N, C]
        batch_size, length, num_nodes, _ = future_data.shape

        # Select input features
        history_data = self.select_input_features(history_data)
        future_data_4_dec = self.select_input_features(future_data)
        
        if not train:
            # For non-training phases, use only temporal features
            future_data_4_dec[..., 0] = torch.empty_like(future_data_4_dec[..., 0])
        # Forward pass through the model
        # model_return = self.model(history_data=history_data, future_data=future_data_4_dec, 
        #                           batch_seen=iter_num, epoch=epoch, train=train)
        model_return = self.model(history_data=history_data, history_t_index=history_t_index)

        # Parse model return
        if isinstance(model_return, torch.Tensor):
            model_return = {'prediction': model_return}
        if 'inputs' not in model_return:
            model_return['inputs'] = self.select_target_features(history_data)
        if 'target' not in model_return:
            model_return['target'] = self.select_target_features(future_data)

        # Ensure the output shape is correct
        assert list(model_return['prediction'].shape)[:3] == [batch_size, length, num_nodes], \
            "The shape of the output is incorrect. Ensure it matches [B, L, N, C]."

        model_return = self.postprocessing(model_return)

        return model_return