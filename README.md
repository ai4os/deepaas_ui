# DEEPaaS UI

> :warning: This is **work-in-progress**, might not work everywhere.

This is a simple User Interface over models served through the [DEEPaaS API](https://github.com/indigo-dc/DEEPaaS). It only wraps the `PREDICT` method, for `TRAIN` you still have to go through the DEEPaaS API.

The motivation was to provide the end user with a friendlier endpoint than the Swagger UI.  It is built with the [Gradio](https://github.com/gradio-app/gradio) package, that enables to easily create interfaces to any ML model (or any function for that matter).

To use it, first install the requirements:
```bash
pip install requirements.txt
```

then run providing the API endpoint you want to interface (default to http://0.0.0.0:5000/) and UI port (default 8000):
```bash
python launch.py --api_url http://0.0.0.0:5000/ --ui_port 8000
```
If several models are found in the API endpoint we just deploy an interface for the first model found.

> **TODOs**
> * implement additional data types
> * add model metadata in UI
