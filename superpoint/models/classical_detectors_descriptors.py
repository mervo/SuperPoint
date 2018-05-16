import tensorflow as tf
import numpy as np
import cv2

from .base_model import BaseModel
from .utils import box_nms


def classical_detector_descriptor(im, **config):
    im = np.uint8(im)
    if config['method'] == 'sift':
        sift = cv2.xfeatures2d.SIFT_create(nfeatures=1500)
        keypoints, desc = sift.detectAndCompute(im, None)
        responses = np.array([k.response for k in keypoints])
        keypoints = np.array([k.pt for k in keypoints]).astype(int)
        desc = np.array(desc)

        detections = np.zeros(im.shape[:2], np.float)
        detections[keypoints[:, 1], keypoints[:, 0]] = responses
        descriptors = np.zeros((im.shape[0], im.shape[1], 128), np.float)
        descriptors[keypoints[:, 1], keypoints[:, 0]] = desc

    elif config['method'] == 'orb':
        orb = cv2.ORB_create(nfeatures=1500)
        keypoints, desc = orb.detectAndCompute(im, None)
        responses = np.array([k.response for k in keypoints])
        keypoints = np.array([k.pt for k in keypoints]).astype(int)
        desc = np.array(desc)

        detections = np.zeros(im.shape[:2], np.float)
        detections[keypoints[:, 1], keypoints[:, 0]] = responses
        descriptors = np.zeros((im.shape[0], im.shape[1], 32), np.float)
        descriptors[keypoints[:, 1], keypoints[:, 0]] = desc

    detections = detections.astype(np.float32)
    descriptors = descriptors.astype(np.float32)
    return (detections, descriptors)


class ClassicalDetectorsDescriptors(BaseModel):
    input_spec = {
            'image': {'shape': [None, None, None, 1], 'type': tf.float32}
    }
    default_config = {
            'method': 'sift',  # 'orb'
            'threshold': 0.5,
            'nms': 4,
            'top_k': 300,
    }
    trainable = False

    def _model(self, inputs, mode, **config):
        im = inputs['image']
        with tf.device('/cpu:0'):
            keypoints, descriptors = tf.map_fn(lambda i: tf.py_func(
                lambda x: classical_detector_descriptor(x, **config),
                [i],
                (tf.float32, tf.float32)),
                                               im, [tf.float32, tf.float32])
            prob = keypoints
            prob_nms = prob
            if config['nms']:
                prob_nms = tf.map_fn(lambda p: box_nms(p, config['nms'], min_prob=0.,
                                                       keep_top_k=config['top_k']), prob)
        pred = tf.cast(tf.greater_equal(prob_nms, config['threshold']), tf.int32)
        keypoints = {'prob': prob, 'prob_nms': prob_nms, 'pred': pred}
        return {**keypoints, 'descriptors': descriptors}

    def _loss(self, outputs, inputs, **config):
        raise NotImplementedError

    def _metrics(self, outputs, inputs, **config):
        pred = outputs['pred']
        labels = inputs['keypoint_map']
        precision = tf.reduce_sum(pred*labels) / tf.reduce_sum(pred)
        recall = tf.reduce_sum(pred*labels) / tf.reduce_sum(labels)
        return {'precision': precision, 'recall': recall}
