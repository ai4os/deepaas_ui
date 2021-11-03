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

"""
We use aiohttp instead of requests to avoid adding additional dependencies
to deepaas.
"""

import base64
import inspect
import json
from pathlib import Path
import tempfile

import aiohttp
import asyncio
import click
import gradio as gr

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
    sess = aiohttp.ClientSession()

    async def getspecs():
        async with sess.get(api_url + 'swagger.json') as r:
            specs = await r.json()
        return specs

    loop = asyncio.get_event_loop()
    specs = loop.run_until_complete(getspecs())

    pred_paths = [p for p in specs['paths'].keys() if p.endswith('predict/')]

    p = pred_paths[0]  # FIXME: we are only interfacing the first model found
    print(f'Parsing {Path(p).parent}')
    api_inp = specs['paths'][p]['post']['parameters']
    api_out = specs['paths'][p]['post']['produces']

    # Transform api data types to Gradio data types
    ## Input types
    gr_inp, inp_names, inp_types, media_types = ui_utils.api2gr_inputs(api_inp)

    ## Output types: multiple ouput return
    if api_out == ['application/json']:
        try:
            struct = specs['definitions']['ModelPredictionResponse']['properties']
        except:
            raise Exception("""
            You should define a proper response schema for handling the model output.
            See the docs [1].
            [1] https://docs.deep-hybrid-datacloud.eu/projects/deepaas/en/stable/user/v2-api.html?highlight=schema#deepaas.model.v2.base.BaseModel.schema
            """)
        gr_out = ui_utils.api2gr_outputs(struct)

    ## Output types: single output return # TODO
    # elif api_out == ['image/png']:
    #     pass

    else:
        raise Exception('DEEPaaS API output not supported for rendering.')


    def api_call(*args, **kwargs):

        headers = {'accept': api_out[0]}
        params = dict(zip(inp_names, args))
        files = {}

        # Format some args
        for k, v in params.copy().items():
            if inp_types[k] == 'integer':
                params[k] = int(v)
            if inp_types[k] == 'boolean':   # aiohttp does not accept bools: https://github.com/aio-libs/aiohttp/issues/4874
                params[k] = str(v)
            elif inp_types[k] in ['array']:
                if isinstance(v, str):
                    params[k] = json.loads(f'[{v}]')
            elif inp_types[k] in ['file']:
                media = params.pop(k)
                if media_types[k] == 'video':
                    path = media
                else:
                    path = media.name
    #             files[k] = path  # this worked only for images, but not for audio/video
                files[k] = open(path, 'rb').read()  # aiohttp neads .read()


        async def postpredict():
            async with aiohttp.ClientSession() as sess:
                async with sess.post(api_url + p,
                                     headers=headers,
                                     params=params,
                                     data=files,) as r:
                    rc = await r.content.read()
            rc = rc.decode("utf-8")  # FIXME: this probably has to be adapted for non-json returns
            return r, rc
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        r, rc = loop.run_until_complete(postpredict())
        loop.close()

        # FIXME: Error should probably be shown in frontend
        # Keep an eye on: https://github.com/gradio-app/gradio/issues/204
        if r.status != 200:
            raise Exception(f'HTML {r.status} eror: {rc}')

        # Reorder in Gradio's expected order and format some outputs
        rc = json.loads(rc)
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

            else:
                rout.append(rc[label])

        return rout

    # Get model metadata
    async def getmetadata():
        async with sess.get(f'{api_url}/{Path(p).parent}/') as r:
            metadata = await r.json()
        return metadata
    loop = asyncio.get_event_loop()
    metadata = loop.run_until_complete(getmetadata())

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
