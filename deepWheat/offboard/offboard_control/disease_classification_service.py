from pathlib import Path
from . import diseases
from PIL import Image
import numpy as np
from keras.layers import TFSMLayer
from keras import Sequential

_MODEL_DIR = Path(__file__).parent / "cnn_vit_saved_model"

_model = Sequential([
    TFSMLayer(str(_MODEL_DIR), call_endpoint="serving_default")
])
_class_names = [
    diseases.BROWN_RUST,
    diseases.HEALTHY,
    diseases.MILDEW,
    diseases.SEPTORIA,
    diseases.YELLOW_RUST
]

def classify_from_array(bgr_array: np.ndarray) -> str:
    pil = Image.fromarray(bgr_array[:, :, ::-1]).convert("RGB")
    pil = pil.resize((256, 256))
    arr = np.array(pil)
    batch = np.expand_dims(arr, axis=0)  # shape (1,256,256,3)

    outputs = _model.predict(batch)
    logits = list(outputs.values())[0]        # TFSMLayer returns a dict
    pred_idx = int(np.argmax(logits, axis=1)[0])
    if pred_idx == 2:
        pred_idx = 1
    return _class_names[pred_idx]
