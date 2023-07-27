# Third-party notices

This project integrates FastAPI/Starlette/Pydantic, Redis-py, Prometheus client, PyTorch and Hugging Face Transformers. Exact Python versions are in `requirements.lock`; installations retain each distribution's license files. These dependencies are not copied into this source tree.

The optional local model is [Google FLAN-T5-small](https://huggingface.co/google/flan-t5-small), Apache-2.0, original revision `371f99f1df1429771f01227c93bd662f5eec2480`. `evidence/model-artifacts.json` identifies every required original artifact and SHA-256. Weights are downloaded separately and retain their upstream license and model card. No upstream affiliation is implied.
