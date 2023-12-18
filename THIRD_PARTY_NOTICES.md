# Third-party notices

This project integrates FastAPI/Starlette/Pydantic, Redis-py, Prometheus client, PyTorch and Hugging Face Transformers. Exact Python versions are in `requirements.lock`; installations retain each distribution's license files. These dependencies are not copied into this source tree.

The local model is [Google FLAN-T5-small](https://huggingface.co/google/flan-t5-small), Apache-2.0, original revision `371f99f1df1429771f01227c93bd662f5eec2480`. `evidence/model-artifacts.json` identifies every required original artifact and SHA-256. Weights are downloaded separately. Consult the upstream [model card](https://huggingface.co/google/flan-t5-small/blob/371f99f1df1429771f01227c93bd662f5eec2480/README.md) and [Apache-2.0 license](https://www.apache.org/licenses/LICENSE-2.0) for model terms. No upstream affiliation is implied.

The console uses React, TypeScript, Vite, Vitest, Testing Library and Playwright under their respective upstream licenses. Exact resolved packages are in `frontend/package-lock.json`. The Docker image includes Python, Node during its build stage, and their base operating-system distributions. Redis 7.0.11 uses its upstream BSD-3-Clause license; image distributions preserve package notices.
