# -*- coding: utf-8 -*-

# Copyright 2021 Spanish National Research Council (CSIC)
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import inspect
import functools
from pathlib import Path
import time
import warnings

import click
import gradio as gr
import requests

import ui_utils


@click.command()
@click.option('--api_url',
              default='http://0.0.0.0:5000/',
              help='URL of the DEEPaaS API')
@click.option('--ui_port',
              default=8000,
              help='URL of the deployed UI')
def main(api_url, ui_port):

    # Parse api inference inputs/outputs
    session = requests.Session()

    # Try to connect several times to DEEPaaS because it might take some time to launch
    max_retries, i = 10, 0
    while True:
        try:
            r = session.get(url=api_url + 'swagger.json')
            break
        except Exception:
            if i == max_retries:
                raise Exception("DEEPaaS API not found")
            else:
                time.sleep(5)
                i += 1

    specs = r.json()
    pred_paths = [p for p in specs['paths'].keys() if p.endswith('predict/')]

    p = pred_paths[0]  # FIXME: we are only interfacing the first model found
    # Check if a model is found ("deepaas-test" is dummy placeholder model)
    if '/deepaas-test/' in p:
        raise Exception('No model could be found.')
    print(f'Parsing {Path(p).parent}')

    # Retrieve DEEPaaS input params for predict()
    api_inp = specs['paths'][p]['post']['parameters']
    for i in api_inp:
        # We default type to string because sometimes modules are not using inputs
        # correctly (eg. YOLOV8: "classes" param)
        i['type'] = i.get('type', 'string')

    # Create a Gradio tab for each MIME type
    interfaces = []
    mimes = specs['paths'][p]['post']['produces']
    for mime in mimes:

        # Ignore default mime "*/*"
        if mime == '*/*':
            continue
        print(f"Processing MIME: {mime}")

        # Transform deepaas inputs to Gradio
        gr_inp = ui_utils.api2gr_inputs(api_inp)

        # Transform deepaas outputs to Gradio
        schema = False
        if mime == 'application/json':
            try:
                # Check if the model has a defined schema
                api_out = specs['definitions']['ModelPredictionResponse']['properties']
                gr_out = ui_utils.api2gr_outputs(api_out)
                schema = True
            except Exception:
                warnings.warn("""
                    You should define a proper response schema [1] for handling the model output.
                    Fallback: return raw JSON.
                    [1] https://docs.deep-hybrid-datacloud.eu/projects/deepaas/en/stable/user/v2-api.html?highlight=schema#deepaas.model.v2.base.BaseModel.schema
                    """)
                gr_out = gr.JSON()

        elif mime.startswith('image/'):
            gr_out = gr.Image(type='filepath')

        elif mime.startswith('audio/'):
            gr_out = gr.Audio(type='filepath')

        elif mime.startswith('video/'):
            gr_out = gr.Video()

        elif mime.startswith('application/'):
            gr_out = gr.File()

        else:
            raise Exception(f'DEEPaaS API output MIME not supported for Gradio rendering: {mime}')

        # Create an api call with non-user parameter pre-filled
        api_call = functools.partial(
            ui_utils.api_call,
            api_inp=api_inp,
            gr_out=gr_out,
            url='/'.join(s.strip('/') for s in [api_url, p]),
            mime=mime,
            schema=schema,
            )

        # Get model metadata
        r = session.get(f'{api_url}/{Path(p).parent}/')
        metadata = r.json()

        # Launch Gradio interface
        interface = gr.Interface(
            fn=api_call,
            inputs=gr_inp,
            outputs=gr_out,
            title=metadata.get('name', ''),
            description=inspect.cleandoc(metadata.get('description', '')),
            article=ui_utils.generate_footer(metadata),
            theme=gr.themes.Default(
                primary_hue=gr.themes.colors.cyan,
                ),
            css=".ai4eosc-logo {border-radius: 10px;}",
            )

        interfaces.append(interface)

    # If more than one MIME type is present, create a tabbed interface
    if len(interfaces) > 1:
        interface = gr.TabbedInterface(
            interface_list = interfaces,
            tab_names=mimes,
        )

    interface.launch(
        inline=False,
        inbrowser=True,
        server_name="0.0.0.0",
        server_port=ui_port,
        show_error = True,
        debug=False,
        favicon_path='./favicon.ico'
    )


if __name__ == '__main__':
    main()
