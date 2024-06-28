# This is the file that is ran from Nomad, when we launch a "try-it" job from PAPI

git clone -b nomad https://github.com/ai4os/deepaas_ui
cd deepaas_ui
pip install -r requirements.txt --ignore-installed blinker

#  Defaut installation leads to:
# ```
# ERROR: Cannot uninstall 'blinker'. It is a distutils installed project and
# thus we cannot accurately determine which files belong to it which
# would lead to only a partial uninstall.
# ```
# So we need to add the ignore flag.
# https://stackoverflow.com/questions/53807511/pip-cannot-uninstall-package-it-is-a-distutils-installed-project

nohup deep-start --deepaas &
#  Let deepaas start
sleep 10
python launch.py --api_url http://0.0.0.0:5000/ --ui_port 8000
# TODO: add command to kill after 10 minutes
