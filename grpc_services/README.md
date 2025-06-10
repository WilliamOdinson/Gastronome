# gRPC Module Integration Guide for Gastronome

This module integrates gRPC services within the Gastronome Django-based recommendation system. It efficiently separates computationally intensive tasks, including sentiment classification using DistilBERT and personalized recommendation generation, into dedicated and scalable gRPC services.

## Directory Structure

```bash
grpc_services/
├── __init__.py
├── clients
│   ├── __init__.py
│   ├── inference_client.py
│   └── recommend_client.py
├── inference_pb2_grpc.py   # Auto-generated
├── inference_pb2.py        # Auto-generated
├── protos
│   ├── __init__.py
│   ├── inference.proto
│   └── recommend.proto
├── README.md
├── recommend_pb2_grpc.py   # Auto-generated
├── recommend_pb2.py        # Auto-generated
└── server.py
```

## Compiling Proto Files

Proto files (e.g. `grpc_services/protos/inference.proto`) define the structure of gRPC services and must be compiled into Python modules. From the project's root directory, run:

```bash
python -m grpc_tools.protoc \
    -I grpc_services/protos \
    --python_out=grpc_services \
    --grpc_python_out=grpc_services \
    grpc_services/protos/*.proto
```

> [!NOTE]
>
> If you encounter a `ModuleNotFoundError` related to generated files, adjust the imports inside generated `_pb2_grpc.py` files: Change the following line (e.g., in `grpc_services/inference_pb2_grpc.py`):
>
> ```python
> import inference_pb2 as inference__pb2
> ```
>
> To a relative import:
>
> ```python
> from . import inference_pb2 as inference__pb2
> ```
>
> Perform this step similarly for `recommend_pb2_grpc.py`.

## Running the gRPC Server

Start the server from your project's root directory:

```bash
python -m grpc_services.server
```

Upon successful startup, the server will output:

```
gRPC server ready on :50051
```
