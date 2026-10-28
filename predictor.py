import json
import os
import zipfile
from pathlib import Path
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import numpy as np
import tensorflow as tf

ROOT = Path(__file__).resolve().parent

class Predictor:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory else ROOT/'models'
        if not (self.directory/'gesture_model.keras').exists() and (ROOT/'models.zip').exists():
            self.directory.mkdir(exist_ok=True)
            with zipfile.ZipFile(ROOT/'models.zip') as archive:
                for member in archive.infolist():
                    destination=(self.directory/member.filename).resolve()
                    if not destination.is_relative_to(self.directory.resolve()):
                        raise ValueError('Unsafe model archive path')
                archive.extractall(self.directory)
        self.config = json.loads((self.directory/'deployment.json').read_text())
        self.classes = self.config['classes']
        self.names = self.config['names']
        self.threshold = self.config['threshold']
        self.size = self.config['image_size']
        self.model = tf.keras.models.load_model(self.directory/'gesture_model.keras', compile=False)

    def image(self, path):
        """Match the original TensorFlow decoder and resize; images must be hand crops."""
        x = tf.io.decode_image(tf.io.read_file(str(path)), channels=3, expand_animations=False)
        return self.predict(x)

    def predict(self, rgb):
        x = tf.image.resize(tf.cast(rgb, tf.float32), [self.size,self.size])[None]
        p = self.model(x, training=False).numpy()[0]
        if p.shape != (len(self.classes),) or not np.isfinite(p).all():
            raise ValueError('Invalid model output')
        return p

    def verify(self):
        refs = json.loads((self.directory/'reference_predictions.json').read_text())
        report = []
        for row in refs:
            p = self.image(self.directory/row['file'])
            np.testing.assert_allclose(p,row['scores'],rtol=3e-3,atol=3e-4)
            report.append({'file':row['file'],'true':self.classes[row['label']],
                           'prediction':self.classes[int(p.argmax())],
                           'max_abs_difference':float(np.max(np.abs(p-np.asarray(row['scores']))))})
        return report
