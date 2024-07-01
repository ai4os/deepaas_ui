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


import base64
import inspect
import json
from pathlib import Path
import tempfile
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
    sess = requests.Session()
    r = sess.get(api_url + 'swagger.json')
    specs = r.json()
    pred_paths = [p for p in specs['paths'].keys() if p.endswith('predict/')]

    p = pred_paths[0]  # FIXME: we are only interfacing the first model found
    print(f'Parsing {Path(p).parent}')
    api_inp = specs['paths'][p]['post']['parameters']
    api_out = specs['paths'][p]['post']['produces']

    # TODO: right now we only keep the first response type because we generate the
    # Gradio interface before knowing what will be the response type selected by
    # the user
    # In the future, multiple types might be addressed with Gradio tabs
    api_out = api_out[0]
    # api_out = api_out[1]
    print(f"Processing MIME: {api_out}")

    # Transform deepaas inputs to Gradio
    gr_inp, inp_names, inp_types, media_types = ui_utils.api2gr_inputs(api_inp)

    # Transform deepaas outputs to Gradio
    if api_out == 'application/json':

        try:
            # Check if the model has a defined schema
            struct = specs['definitions']['ModelPredictionResponse']['properties']
            gr_out = ui_utils.api2gr_outputs(struct)
            schema = True
        except Exception:
            warnings.warn("""
            You should define a proper response schema [1] for handling the model output.
            Fallback: return raw JSON.
            [1] https://docs.deep-hybrid-datacloud.eu/projects/deepaas/en/stable/user/v2-api.html?highlight=schema#deepaas.model.v2.base.BaseModel.schema
            """)
            schema = False
            gr_out = [gr.outputs.JSON()]

    elif api_out.startswith('image/'):
        gr_out = [gr.outputs.Image(type='file')]

    elif api_out.startswith('audio/'):
        gr_out = [gr.outputs.Audio(type='file')]

    elif api_out.startswith('video/'):
        gr_out = [gr.outputs.Video(type='mp4')]

    elif api_out.startswith('application/'):
        gr_out = gr.outputs.File()

    else:
        raise Exception(f'DEEPaaS API output MIME not supported for Gradio rendering: {api_out}')


    def api_call(*args, **kwargs):

        headers = {'accept': api_out}
        params = dict(zip(inp_names, args))
        files = {}

        # Format some args
        for k, v in params.copy().items():
            if inp_types[k] == 'integer':
                params[k] = int(v)
            elif inp_types[k] in ['array']:
                if isinstance(v, str):
                    params[k] = json.loads(f'[{v}]')
            elif inp_types[k] in ['file']:
                media = params.pop(k)
                if media_types[k] == 'video':
                    path = media
                else:
                    path = media.name
                # files[k] = path  # this worked only for images, but not for audio/video
                files[k] = open(path, 'rb')

        # We also send accept as a param in case the module does different post
        # processing based on this parameter.
        # Accept is hardcoded because the user does not get to choose it.
        params['accept'] = api_out

        r = sess.post(api_url + p,
                      headers=headers,
                      params=params,
                      files=files,
                      verify=False)

        if api_out == 'application/json':
            rc = r.content.decode("utf-8")

            # FIXME: Error should probably be shown in frontend
            # Keep an eye on: https://github.com/gradio-app/gradio/issues/204
            if r.status_code != 200:
                raise Exception(f'HTML {r.status_code} error: {rc}')

            rc = json.loads(rc)

            # If schema is provided, reorder outputs in Gradio's expected order
            # and format outputs (if needed)
            if schema:
                rout = []
                for arg in gr_out:
                    label = arg.label

                    # Handle classification outputs
                    if label == 'classification scores':
                        rout.append(dict(zip(rc['labels'],
                                            rc['probabilities'])
                                        )
                                )

                    # Process media files
                    elif isinstance(arg, (gr.outputs.Image,
                                        gr.outputs.Audio,
                                        gr.outputs.Video)):
                        media = rc[label].encode('utf-8')  # bytes
                        media = base64.b64decode(media)  # bytes
                        suffix = '.mp4' if isinstance(arg, gr.outputs.Video) else None
                        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fp:
                            fp.write(media)
                        media = fp.name
                        rout.append(media)

                    elif isinstance(arg, gr.outputs.Textbox) and arg.type=='str':
                        # see webargs.Field param
                        rout.append(str(rc[label]))

                    else:
                        rout.append(rc[label])

            else:
                # If no schema provided return everything as a JSON
                rout = rc['predictions']

        else:
            # Process non-json responses: save to file and return path
            ftype = ui_utils.find_filetype(api_out)
            with tempfile.NamedTemporaryFile(suffix=f".{ftype}", delete=False) as fp:
                fp.write(r.content)
            rout = fp.name

        return rout


    # Get model metadata
    r = sess.get(f'{api_url}/{Path(p).parent}/')
    metadata = r.json()

    # Launch Gradio interface
    iface = gr.Interface(
        fn=api_call,
        inputs=gr_inp,
        outputs=gr_out,
        title=metadata.get('name', ''),
        description=inspect.cleandoc(metadata.get('description', '')),
        article=ui_utils.generate_footer(metadata),
        theme='grass',
        server_name="0.0.0.0",
        server_port=ui_port,
    )

    iface.launch(
        inline=False,
        inbrowser=True,
        debug=False,  #FIXME: remove debug for production
    )


if __name__ == '__main__':
    main()
