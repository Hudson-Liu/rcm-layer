#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
basic_cifar.py: Compares the RCM layer accuracy to the Dense layer accuracy on the CIFAR-100 dataset. 
The code is heavily based off the example code provided by Keras.
"""

__author__ = "Hudson Liu"
__email__ = "hudsonliu0@gmail.com"

import numpy as np
import os
import shutil
from keras.layers import (
    Conv2D,
    MaxPooling2D,
    Flatten,
    Dropout,
    Dense,
    BatchNormalization
)
import tensorflow as tf

# NOTE: This script must be executed from the "examples" module-level, as __init__.py must be executed prior
from rcm_layer import RCM, ActivationTable

# Defines Model Hyperparameters
NUM_CLASSES = 100
INPUT_SHAPE = (32, 32, 3)
BATCH_SIZE = 128
EPOCHS = 600
HIDDEN_UNITS = 100
RCM_OUTPUTS = 100
NUM_PROPAGATIONS = 5
NORMALIZATION = None
OPTIMIZER = "adam"
DENSE_NORM = True # Whether normalization should be applied to the standard dense layer

# Load MNIST dataset
(x_train, y_train), (x_test, y_test) = tf.keras.datasets.cifar100.load_data()

# Preprocess data
x_train = x_train.astype("float32") / 255
x_test = x_test.astype("float32") / 255
x_train = np.expand_dims(x_train, -1)
x_test = np.expand_dims(x_test, -1)
y_train = tf.keras.utils.to_categorical(y_train, NUM_CLASSES)
y_test = tf.keras.utils.to_categorical(y_test, NUM_CLASSES)

def equivalent_dense_nodes(input_nodes: int, hidden_units: int, rcm_outputs: int, final_outputs: int) -> int:
    """Calculates the necessary number of hidden Dense nodes needed to equal the same number of parameters as the RCM layer"""
    return ((input_nodes + hidden_units + rcm_outputs) ** 2  + (rcm_outputs * final_outputs)) // (input_nodes + final_outputs)

def create_model(model_type: str) -> tf.keras.Model:
    """Creates a model with either an RCM or Dense layer"""
    # Create convolutional filters and flatten
    inputs = tf.keras.Input(shape=INPUT_SHAPE)
    convs = Conv2D(32, (3,3), activation='relu')(inputs)
    pool = MaxPooling2D(2,2)(convs)
    convs = Conv2D(64, (3,3), activation='relu')(pool)
    pool = MaxPooling2D(2,2)(convs)
    convs = Conv2D(64, (3,3), activation='relu')(pool)
    pool = MaxPooling2D(2,2)(convs)
    flatten = Flatten()(pool)
    dropout = Dropout(0.5)(flatten)

    # Creates either a Dense layer or an RCM layer
    if model_type == "rcm":
        layer = RCM(
            hidden_units=HIDDEN_UNITS, 
            output_units=NUM_CLASSES,
            num_propagations=NUM_PROPAGATIONS, 
            activations="relu",
            normalization_position=NORMALIZATION
        )(dropout)
        norm = BatchNormalization()(layer)
    elif model_type == "dense":
        nodes = equivalent_dense_nodes(
            dropout.get_shape()[-1], 
            HIDDEN_UNITS,
            RCM_OUTPUTS, 
            NUM_CLASSES
        )
        norm = BatchNormalization()(dropout)
        layer = Dense(nodes, activation="relu")(norm if DENSE_NORM else dropout)
        norm = BatchNormalization()(layer)
    else:
        raise ValueError(f"'model_type' must either be 'rcm' or 'dense', got {model_type}.")
    
    # Adds a final output layer
    outputs = Dense(NUM_CLASSES, activation="softmax")(norm if DENSE_NORM else layer)
    
    # Returns final model
    return tf.keras.Model(inputs, outputs)

# Runs both a Dense layer model and an RCM layer model to compare accuracies
MODEL_TYPES = ["dense"]
for model_type in MODEL_TYPES:
    # Creates a model of the specified model type
    model = create_model(model_type)
    model.compile(
        loss=tf.keras.losses.CategoricalCrossentropy(),
        optimizer=OPTIMIZER,
        metrics=["accuracy"],
    )

    # Create filename
    dense_norm_str = "DenseNorm" if DENSE_NORM else "NoDenseNorm"
    filename = f"CIFAR_{EPOCHS}_{HIDDEN_UNITS}_{model_type}_{OPTIMIZER}_{dense_norm_str}"
    log_dir = f"models/logs/fit/{filename}"

    # Creates visualizations and logs
    tf.keras.utils.plot_model(model, to_file=f"models/CIFAR_{model_type}.png", show_shapes=True)
    if model_type == "rcm":
        log_dir += f"_{NUM_PROPAGATIONS}_{NORMALIZATION}"
    if os.path.exists(log_dir) and os.path.isdir(log_dir):
        shutil.rmtree(log_dir)
    tensorboard_callback = tf.keras.callbacks.TensorBoard(log_dir=log_dir, histogram_freq=1)

    # Trains model
    model.fit(x_train, y_train, batch_size=BATCH_SIZE, epochs=EPOCHS, validation_split=0.1, callbacks=[tensorboard_callback])
    
    # Evaluates model on test set
    score = model.evaluate(x_test, y_test, verbose=0)
    print(f"{model_type} test loss:", score[0])
    print(f"{model_type} test accuracy:", score[1])

    # Save model in SavedModel format
    model.save(f"models/{filename}")
