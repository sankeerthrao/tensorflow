# Copyright 2018 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
# pylint: disable=protected-access
"""Tests for saving/loading function for keras Model."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import shutil

from absl.testing import parameterized
import numpy as np

from tensorflow.python import keras
from tensorflow.python import tf2
from tensorflow.python.client import session
from tensorflow.python.eager import context
from tensorflow.python.framework import constant_op
from tensorflow.python.framework import dtypes
from tensorflow.python.framework import ops
from tensorflow.python.framework import tensor_spec
from tensorflow.python.framework import test_util
from tensorflow.python.keras import keras_parameterized
from tensorflow.python.keras import regularizers
from tensorflow.python.keras import testing_utils
from tensorflow.python.keras.engine import training as model_lib
from tensorflow.python.keras.optimizer_v2 import adadelta
from tensorflow.python.keras.saving import saved_model as keras_saved_model
from tensorflow.python.keras.utils import mode_keys
from tensorflow.python.keras.utils import tf_utils
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import init_ops
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import variables
from tensorflow.python.platform import test
from tensorflow.python.saved_model import load as tf_load
from tensorflow.python.saved_model import loader_impl
from tensorflow.python.saved_model import model_utils
from tensorflow.python.saved_model import save as tf_save
from tensorflow.python.training import training as training_module


class TestModelSavingandLoading(test.TestCase):

  def _save_model_dir(self, dirname='saved_model'):
    temp_dir = self.get_temp_dir()
    self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
    return os.path.join(temp_dir, dirname)

  def test_saving_sequential_model(self):
    with self.cached_session():
      model = keras.models.Sequential()
      model.add(keras.layers.Dense(2, input_shape=(3,)))
      model.add(keras.layers.RepeatVector(3))
      model.add(keras.layers.TimeDistributed(keras.layers.Dense(3)))
      model.compile(
          loss=keras.losses.MSE,
          optimizer=keras.optimizers.RMSprop(lr=0.0001),
          metrics=[keras.metrics.categorical_accuracy],
          sample_weight_mode='temporal')
      x = np.random.random((1, 3))
      y = np.random.random((1, 3, 3))
      model.train_on_batch(x, y)

      ref_y = model.predict(x)

      saved_model_dir = self._save_model_dir()
      keras_saved_model.export_saved_model(model, saved_model_dir)

      loaded_model = keras_saved_model.load_from_saved_model(saved_model_dir)
      y = loaded_model.predict(x)
      self.assertAllClose(ref_y, y, atol=1e-05)

  @test_util.run_in_graph_and_eager_modes
  def test_saving_sequential_model_without_compile(self):
    with self.cached_session():
      model = keras.models.Sequential()
      model.add(keras.layers.Dense(2, input_shape=(3,)))
      model.add(keras.layers.RepeatVector(3))
      model.add(keras.layers.TimeDistributed(keras.layers.Dense(3)))

      x = np.random.random((1, 3))
      ref_y = model.predict(x)

      saved_model_dir = self._save_model_dir()
      keras_saved_model.export_saved_model(model, saved_model_dir)
      loaded_model = keras_saved_model.load_from_saved_model(saved_model_dir)

      y = loaded_model.predict(x)
      self.assertAllClose(ref_y, y, atol=1e-05)

  def test_saving_functional_model(self):
    with self.cached_session():
      inputs = keras.layers.Input(shape=(3,))
      x = keras.layers.Dense(2)(inputs)
      output = keras.layers.Dense(3)(x)

      model = keras.models.Model(inputs, output)
      model.compile(
          loss=keras.losses.MSE,
          optimizer=keras.optimizers.RMSprop(lr=0.0001),
          metrics=[keras.metrics.categorical_accuracy])
      x = np.random.random((1, 3))
      y = np.random.random((1, 3))
      model.train_on_batch(x, y)

      ref_y = model.predict(x)

      saved_model_dir = self._save_model_dir()
      keras_saved_model.export_saved_model(model, saved_model_dir)
      loaded_model = keras_saved_model.load_from_saved_model(saved_model_dir)

      y = loaded_model.predict(x)
      self.assertAllClose(ref_y, y, atol=1e-05)

  @test_util.run_in_graph_and_eager_modes
  def test_saving_functional_model_without_compile(self):
    with self.cached_session():
      inputs = keras.layers.Input(shape=(3,))
      x = keras.layers.Dense(2)(inputs)
      output = keras.layers.Dense(3)(x)

      model = keras.models.Model(inputs, output)

      x = np.random.random((1, 3))
      y = np.random.random((1, 3))

      ref_y = model.predict(x)

      saved_model_dir = self._save_model_dir()
      keras_saved_model.export_saved_model(model, saved_model_dir)
      loaded_model = keras_saved_model.load_from_saved_model(saved_model_dir)

      y = loaded_model.predict(x)
      self.assertAllClose(ref_y, y, atol=1e-05)

  @test_util.run_in_graph_and_eager_modes
  def test_saving_with_tf_optimizer(self):
    model = keras.models.Sequential()
    model.add(keras.layers.Dense(2, input_shape=(3,)))
    model.add(keras.layers.Dense(3))
    model.compile(
        loss='mse',
        optimizer=training_module.RMSPropOptimizer(0.1),
        metrics=['acc'])

    x = np.random.random((1, 3))
    y = np.random.random((1, 3))
    model.train_on_batch(x, y)
    ref_y = model.predict(x)

    saved_model_dir = self._save_model_dir()
    keras_saved_model.export_saved_model(model, saved_model_dir)
    loaded_model = keras_saved_model.load_from_saved_model(saved_model_dir)
    loaded_model.compile(
        loss='mse',
        optimizer=training_module.RMSPropOptimizer(0.1),
        metrics=['acc'])
    y = loaded_model.predict(x)
    self.assertAllClose(ref_y, y, atol=1e-05)

    # test that new updates are the same with both models
    x = np.random.random((1, 3))
    y = np.random.random((1, 3))

    ref_loss = model.train_on_batch(x, y)
    loss = loaded_model.train_on_batch(x, y)
    self.assertAllClose(ref_loss, loss, atol=1e-05)

    ref_y = model.predict(x)
    y = loaded_model.predict(x)
    self.assertAllClose(ref_y, y, atol=1e-05)

    # test saving/loading again
    saved_model_dir2 = self._save_model_dir('saved_model_2')
    keras_saved_model.export_saved_model(loaded_model, saved_model_dir2)
    loaded_model = keras_saved_model.load_from_saved_model(saved_model_dir2)
    y = loaded_model.predict(x)
    self.assertAllClose(ref_y, y, atol=1e-05)

  def test_saving_subclassed_model_raise_error(self):
    # For now, saving subclassed model should raise an error. It should be
    # avoided later with loading from SavedModel.pb.

    class SubclassedModel(model_lib.Model):

      def __init__(self):
        super(SubclassedModel, self).__init__()
        self.layer1 = keras.layers.Dense(3)
        self.layer2 = keras.layers.Dense(1)

      def call(self, inp):
        return self.layer2(self.layer1(inp))

    model = SubclassedModel()

    saved_model_dir = self._save_model_dir()
    with self.assertRaises(NotImplementedError):
      keras_saved_model.export_saved_model(model, saved_model_dir)


class LayerWithLearningPhase(keras.engine.base_layer.Layer):

  def build(self, input_shape):
    self.input_spec = keras.layers.InputSpec(shape=[None] * len(input_shape))
    self.built = True

  def call(self, x, training=None):
    if training is None:
      training = keras.backend.learning_phase()
    output = tf_utils.smart_cond(
        training, lambda: x * 0, lambda: array_ops.identity(x))
    if not context.executing_eagerly():
      output._uses_learning_phase = True  # pylint: disable=protected-access
    return output

  def compute_output_shape(self, input_shape):
    return input_shape


def functional_model(uses_learning_phase=True):
  inputs = keras.layers.Input(shape=(3,))
  x = keras.layers.Dense(2)(inputs)
  x = keras.layers.Dense(3)(x)
  if uses_learning_phase:
    x = LayerWithLearningPhase()(x)
  return keras.models.Model(inputs, x)


def sequential_model(uses_learning_phase=True):
  model = keras.models.Sequential()
  model.add(keras.layers.Dense(2, input_shape=(3,)))
  model.add(keras.layers.Dense(3))
  if uses_learning_phase:
    model.add(LayerWithLearningPhase())
  return model


def sequential_model_without_input_shape(uses_learning_phase=True):
  model = keras.models.Sequential()
  model.add(keras.layers.Dense(2))
  model.add(keras.layers.Dense(3))
  if uses_learning_phase:
    model.add(LayerWithLearningPhase())
  return model


class Subclassed(keras.models.Model):

  def __init__(self):
    super(Subclassed, self).__init__()
    self.dense1 = keras.layers.Dense(2)
    self.dense2 = keras.layers.Dense(3)

  def call(self, inputs):
    x = self.dense1(inputs)
    x = self.dense2(x)
    return x


def subclassed_model():
  return Subclassed()


def load_model(sess, path, mode):
  tags = model_utils.EXPORT_TAG_MAP[mode]
  sig_def_key = model_utils.SIGNATURE_KEY_MAP[mode]

  meta_graph_def = loader_impl.load(sess, tags, path)
  inputs = {
      k: sess.graph.get_tensor_by_name(v.name)
      for k, v in meta_graph_def.signature_def[sig_def_key].inputs.items()}
  outputs = {
      k: sess.graph.get_tensor_by_name(v.name)
      for k, v in meta_graph_def.signature_def[sig_def_key].outputs.items()}
  return inputs, outputs, meta_graph_def


@test_util.run_all_in_graph_and_eager_modes
class TestModelSavedModelExport(test.TestCase, parameterized.TestCase):

  def _save_model_dir(self, dirname='saved_model'):
    temp_dir = self.get_temp_dir()
    self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
    return os.path.join(temp_dir, dirname)

  @parameterized.parameters(
      {
          'model_builder': functional_model,
          'uses_learning_phase': True,
          'optimizer_cls': adadelta.Adadelta,
          'train_before_export': True},
      {
          'model_builder': functional_model,
          'uses_learning_phase': True,
          'optimizer_cls': training_module.AdadeltaOptimizer,
          'train_before_export': False},
      {
          'model_builder': functional_model,
          'uses_learning_phase': False,
          'optimizer_cls': None,
          'train_before_export': False},
      {
          'model_builder': sequential_model,
          'uses_learning_phase': True,
          'optimizer_cls': training_module.AdadeltaOptimizer,
          'train_before_export': True},
      {
          'model_builder': sequential_model,
          'uses_learning_phase': True,
          'optimizer_cls': adadelta.Adadelta,
          'train_before_export': False},
      {
          'model_builder': sequential_model,
          'uses_learning_phase': False,
          'optimizer_cls': None,
          'train_before_export': False},
      {
          'model_builder': sequential_model_without_input_shape,
          'uses_learning_phase': True,
          'optimizer_cls': training_module.AdadeltaOptimizer,
          'train_before_export': False})
  def testSaveAndLoadSavedModelExport(
      self, model_builder, uses_learning_phase, optimizer_cls,
      train_before_export):
    optimizer = None if optimizer_cls is None else optimizer_cls()

    saved_model_dir = self._save_model_dir()

    np.random.seed(130)
    input_arr = np.random.random((1, 3))
    target_arr = np.random.random((1, 3))

    model = model_builder(uses_learning_phase)
    if optimizer is not None:
      model.compile(
          loss='mse',
          optimizer=optimizer,
          metrics=['mae'])
      if train_before_export:
        model.train_on_batch(input_arr, target_arr)

      ref_loss, ref_mae = model.evaluate(input_arr, target_arr)

    ref_predict = model.predict(input_arr)

    # Export SavedModel
    keras_saved_model.export_saved_model(model, saved_model_dir)

    input_name = model.input_names[0]
    output_name = model.output_names[0]
    target_name = output_name + '_target'

    # Load predict graph, and test predictions
    with session.Session(graph=ops.Graph()) as sess:
      inputs, outputs, _ = load_model(sess, saved_model_dir,
                                      mode_keys.ModeKeys.PREDICT)

      predictions = sess.run(outputs[output_name],
                             {inputs[input_name]: input_arr})
      self.assertAllClose(ref_predict, predictions, atol=1e-05)

    if optimizer:
      # Load eval graph, and test predictions, loss and metric values
      with session.Session(graph=ops.Graph()) as sess:
        inputs, outputs, _ = load_model(sess, saved_model_dir,
                                        mode_keys.ModeKeys.TEST)

        # First obtain the loss and predictions, and run the metric update op by
        # feeding in the inputs and targets.
        metrics_name = 'mae' if tf2.enabled() else 'mean_absolute_error'
        metrics_update_op_key = 'metrics/' + metrics_name + '/update_op'
        metrics_value_op_key = 'metrics/' + metrics_name + '/value'

        loss, predictions, _ = sess.run(
            (outputs['loss'], outputs['predictions/' + output_name],
             outputs[metrics_update_op_key]), {
                 inputs[input_name]: input_arr,
                 inputs[target_name]: target_arr
             })

        # The metric value should be run after the update op, to ensure that it
        # reflects the correct value.
        metric_value = sess.run(outputs[metrics_value_op_key])

        self.assertEqual(int(train_before_export),
                         sess.run(training_module.get_global_step()))
        self.assertAllClose(ref_loss, loss, atol=1e-05)
        self.assertAllClose(ref_mae, metric_value, atol=1e-05)
        self.assertAllClose(ref_predict, predictions, atol=1e-05)

      # Load train graph, and check for the train op, and prediction values
      with session.Session(graph=ops.Graph()) as sess:
        inputs, outputs, meta_graph_def = load_model(
            sess, saved_model_dir, mode_keys.ModeKeys.TRAIN)
        self.assertEqual(int(train_before_export),
                         sess.run(training_module.get_global_step()))
        self.assertIn('loss', outputs)
        self.assertIn(metrics_update_op_key, outputs)
        self.assertIn(metrics_value_op_key, outputs)
        self.assertIn('predictions/' + output_name, outputs)

        # Train for a step
        train_op = loader_impl.get_train_op(meta_graph_def)
        train_outputs, _ = sess.run(
            [outputs, train_op], {inputs[input_name]: input_arr,
                                  inputs[target_name]: target_arr})
        self.assertEqual(int(train_before_export) + 1,
                         sess.run(training_module.get_global_step()))

        if uses_learning_phase:
          self.assertAllClose(
              [[0, 0, 0]], train_outputs['predictions/' + output_name],
              atol=1e-05)
        else:
          self.assertNotAllClose(
              [[0, 0, 0]], train_outputs['predictions/' + output_name],
              atol=1e-05)

  def testSaveAndLoadSavedModelWithCustomObject(self):
    saved_model_dir = self._save_model_dir()
    with session.Session(graph=ops.Graph()) as sess:
      def relu6(x):
        return keras.backend.relu(x, max_value=6)
      inputs = keras.layers.Input(shape=(1,))
      outputs = keras.layers.Activation(relu6)(inputs)
      model = keras.models.Model(inputs, outputs)
      keras_saved_model.export_saved_model(
          model, saved_model_dir, custom_objects={'relu6': relu6})
    with session.Session(graph=ops.Graph()) as sess:
      inputs, outputs, _ = load_model(sess, saved_model_dir,
                                      mode_keys.ModeKeys.PREDICT)
      input_name = model.input_names[0]
      output_name = model.output_names[0]
      predictions = sess.run(
          outputs[output_name], {inputs[input_name]: [[7], [-3], [4]]})
      self.assertAllEqual([[6], [0], [4]], predictions)

  def testAssertModelCloneSameObjectsIgnoreOptimizer(self):
    input_arr = np.random.random((1, 3))
    target_arr = np.random.random((1, 3))

    model_graph = ops.Graph()
    clone_graph = ops.Graph()

    # Create two models with the same layers but different optimizers.
    with session.Session(graph=model_graph):
      inputs = keras.layers.Input(shape=(3,))
      x = keras.layers.Dense(2)(inputs)
      x = keras.layers.Dense(3)(x)
      model = keras.models.Model(inputs, x)

      model.compile(loss='mse', optimizer=training_module.AdadeltaOptimizer())
      model.train_on_batch(input_arr, target_arr)

    with session.Session(graph=clone_graph):
      inputs = keras.layers.Input(shape=(3,))
      x = keras.layers.Dense(2)(inputs)
      x = keras.layers.Dense(3)(x)
      clone = keras.models.Model(inputs, x)
      clone.compile(loss='mse', optimizer=keras.optimizers.RMSprop(lr=0.0001))
      clone.train_on_batch(input_arr, target_arr)

    keras_saved_model._assert_same_non_optimizer_objects(
        model, model_graph, clone, clone_graph)

  def testAssertModelCloneSameObjectsThrowError(self):
    input_arr = np.random.random((1, 3))
    target_arr = np.random.random((1, 3))

    model_graph = ops.Graph()
    clone_graph = ops.Graph()

    # Create two models with the same layers but different optimizers.
    with session.Session(graph=model_graph):
      inputs = keras.layers.Input(shape=(3,))
      x = keras.layers.Dense(2)(inputs)
      x = keras.layers.Dense(3)(x)
      model = keras.models.Model(inputs, x)

      model.compile(loss='mse', optimizer=training_module.AdadeltaOptimizer())
      model.train_on_batch(input_arr, target_arr)

    with session.Session(graph=clone_graph):
      inputs = keras.layers.Input(shape=(3,))
      x = keras.layers.Dense(2)(inputs)
      x = keras.layers.Dense(4)(x)
      x = keras.layers.Dense(3)(x)
      clone = keras.models.Model(inputs, x)
      clone.compile(loss='mse', optimizer=keras.optimizers.RMSprop(lr=0.0001))
      clone.train_on_batch(input_arr, target_arr)

  def testSaveSequentialModelWithoutInputShapes(self):
    model = sequential_model_without_input_shape(True)
    # A Sequential model that hasn't been built should raise an error.
    with self.assertRaisesRegexp(
        ValueError, 'Weights for sequential model have not yet been created'):
      keras_saved_model.export_saved_model(model, '')

    # Even with input_signature, the model's weights has not been created.
    with self.assertRaisesRegexp(
        ValueError, 'Weights for sequential model have not yet been created'):
      saved_model_dir = self._save_model_dir()
      keras_saved_model.export_saved_model(
          model,
          saved_model_dir,
          input_signature=tensor_spec.TensorSpec(
              shape=(10, 11, 12, 13, 14), dtype=dtypes.float32,
              name='spec_input'))

  @parameterized.parameters(
      {
          'model_builder': sequential_model_without_input_shape,
          'input_signature': [tensor_spec.TensorSpec(shape=[None, 3],
                                                     dtype=dtypes.float32)]},
      {
          'model_builder': subclassed_model,
          'input_signature': [tensor_spec.TensorSpec(shape=[None, 3],
                                                     dtype=dtypes.float32)]})
  def testServingOnly(self, model_builder, input_signature):
    if context.executing_eagerly():
      saved_model_dir = self._save_model_dir()
      input_arr = np.random.random((5, 3)).astype(np.float32)
      model = model_builder()
      ref_predict = model.predict(input_arr)

      keras_saved_model.export_saved_model(
          model,
          saved_model_dir,
          serving_only=True,
          input_signature=input_signature)

      # Load predict graph, and test predictions
      with session.Session(graph=ops.Graph()) as sess:
        inputs, outputs, _ = load_model(sess, saved_model_dir,
                                        mode_keys.ModeKeys.PREDICT)
        predictions = sess.run(outputs[next(iter(outputs.keys()))],
                               {inputs[next(iter(inputs.keys()))]: input_arr})
        self.assertAllClose(ref_predict, predictions, atol=1e-05)


@test_util.run_all_in_graph_and_eager_modes
class TestModelSavingAndLoadingV2(keras_parameterized.TestCase):

  def _save_model_dir(self, dirname='saved_model'):
    temp_dir = self.get_temp_dir()
    self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
    return os.path.join(temp_dir, dirname)

  @keras_parameterized.run_with_all_model_types
  def test_model_save_and_load(self):
    input_arr = np.random.random((1, 3)).astype(np.float32)
    target_arr = np.random.random((1, 4)).astype(np.float32)

    model = testing_utils.get_small_mlp(1, 4, input_dim=3)
    model.layers[-1].activity_regularizer = regularizers.get('l2')
    model.activity_regularizer = regularizers.get('l2')
    model.compile(
        loss='mse',
        optimizer='rmsprop')
    model.train_on_batch(input_arr, target_arr)

    def callable_loss():
      return math_ops.reduce_sum(model.weights[0])
    model.add_loss(callable_loss)
    saved_model_dir = self._save_model_dir()
    tf_save.save(model, saved_model_dir)

    loaded = keras_saved_model.load_from_saved_model_v2(saved_model_dir)
    self.evaluate(variables.variables_initializer(loaded.variables))
    self.assertAllClose(self.evaluate(model.weights),
                        self.evaluate(loaded.weights))

    input_arr = constant_op.constant(
        np.random.random((1, 3)).astype(np.float32))
    self.assertAllClose(self.evaluate(model(input_arr)),
                        self.evaluate(loaded(input_arr)))
    # Validate losses. The order of conditional losses may change between the
    # model and loaded model, so sort the losses first.
    if context.executing_eagerly():
      self.assertAllClose(sorted(self.evaluate(model.losses)),
                          sorted(self.evaluate(loaded.losses)))
    else:
      self.assertAllClose(self.evaluate(model.get_losses_for(None)),
                          self.evaluate(loaded.get_losses_for(None)))
      self.assertAllClose(
          sorted(self.evaluate(model.get_losses_for(input_arr))),
          sorted(self.evaluate(loaded.get_losses_for(input_arr))))

  def test_trainable_weights(self):
    layer = keras.layers.Dense(4, name='custom_layer')
    layer.build([3,])
    layer.add_weight(
        'extra_weight', shape=[],
        initializer=init_ops.constant_initializer(11),
        trainable=True)
    layer.add_weight(
        'extra_weight_2', shape=[],
        initializer=init_ops.constant_initializer(12),
        trainable=False)

    saved_model_dir = self._save_model_dir()
    self.evaluate(variables.variables_initializer(layer.variables))
    tf_save.save(layer, saved_model_dir)
    loaded = keras_saved_model.load_from_saved_model_v2(saved_model_dir)
    self.evaluate(variables.variables_initializer(loaded.variables))

    equal_attrs = ['name', '_expects_training_arg', 'trainable']
    for attr in equal_attrs:
      self.assertEqual(getattr(layer, attr), getattr(loaded, attr))

    all_close = ['weights', 'trainable_weights', 'non_trainable_weights']
    for attr in all_close:
      self.assertAllClose(self.evaluate(getattr(layer, attr)),
                          self.evaluate(getattr(loaded, attr)))

  def test_maintains_losses(self):
    """Tests that the layer losses do not change before and after export."""

    class LayerWithLoss(keras.layers.Layer):

      def call(self, inputs):
        self.add_loss(math_ops.reduce_sum(inputs), inputs)
        return inputs

    model = keras.models.Sequential([LayerWithLoss()])
    model.compile(
        loss='mse',
        optimizer='rmsprop')
    input_arr = np.random.random((1, 3)).astype(np.float32)
    target_arr = np.random.random((1, 3)).astype(np.float32)

    # Test that symbolic losses are maintained (train_on_batch saves symbolic
    # losses.)
    model.train_on_batch(input_arr, target_arr)
    previous_losses = model.losses[:]

    saved_model_dir = self._save_model_dir()
    tf_save.save(model, saved_model_dir)
    self.assertAllEqual(previous_losses, model.losses)

    if context.executing_eagerly():
      # Test that eager losses are maintained.
      model(input_arr)  # Calls model eagerly, creating eager losses.
      previous_losses = model.losses[:]
      tf_save.save(model, saved_model_dir)
      self.assertAllEqual(previous_losses, model.losses)

  def test_layer_with_learning_phase(self):
    layer = LayerWithLearningPhase()
    layer.build([None, None])
    saved_model_dir = self._save_model_dir()
    tf_save.save(layer, saved_model_dir)
    loaded = keras_saved_model.load_from_saved_model_v2(saved_model_dir)
    input_arr = array_ops.ones((4, 3))

    # Run the layer, and use the keras backend learing phase
    keras.backend.set_learning_phase(0)
    self.assertAllEqual(input_arr, loaded(input_arr))
    keras.backend.set_learning_phase(1)
    self.assertAllEqual(array_ops.zeros((4, 3)), loaded(input_arr))

    # Run the layer while explicitly setting the training argument
    self.assertAllEqual(
        input_arr, loaded(input_arr, training=constant_op.constant(False)))
    self.assertAllEqual(
        array_ops.zeros((4, 3)),
        loaded(input_arr, training=constant_op.constant(True)))

  @keras_parameterized.run_with_all_model_types
  def test_standard_loader(self):
    model = testing_utils.get_small_mlp(1, 4, input_dim=3)
    model.activity_regularizer = regularizers.get('l2')
    def eager_loss():
      return math_ops.reduce_sum(model.weights[0])
    model.add_loss(eager_loss)

    # Call predict to ensure that all layers are built and inputs are set.
    model.predict(np.random.random((1, 3)))
    saved_model_dir = self._save_model_dir()

    tf_save.save(model, saved_model_dir)

    loaded = tf_load.load(saved_model_dir)
    self.evaluate(variables.variables_initializer(loaded.variables))
    all_close = ['variables', 'trainable_variables',
                 'non_trainable_variables']
    for attr in all_close:
      self.assertAllClose(self.evaluate(getattr(model, attr)),
                          self.evaluate(getattr(loaded.keras_api, attr)))
    self.assertLen(loaded.regularization_losses, 1)
    expected_layers = len(model.layers)
    if testing_utils.get_model_type() == 'sequential':
      # The autogenerated Input layer is hidden in the model.layers list,
      # but included in the loaded sub-layers.
      expected_layers += 1
    self.assertEqual(expected_layers, len(loaded.keras_api.layers))
    input_arr = array_ops.ones((4, 3))
    training_bool = constant_op.constant(False)

    if model._expects_training_arg:
      call_args = [input_arr, training_bool]
    else:
      call_args = [input_arr]
    self.assertAllClose(self.evaluate(model(input_arr)),
                        self.evaluate(loaded(*call_args)))

if __name__ == '__main__':
  test.main()
