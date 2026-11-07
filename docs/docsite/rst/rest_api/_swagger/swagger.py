"""Assets for the REST API reference page (rest_api/api_ref).

The page renders Belfry's OpenAPI 3 schema with Swagger UI. The schema is
rst/open_api/schema.json, which download-json.py takes from the latest Belfry
release; it is copied to _static/schema.json.

Swagger UI is vendored from the npm package swagger-ui-dist 5.34.1
(https://registry.npmjs.org/swagger-ui-dist/-/swagger-ui-dist-5.34.1.tgz,
integrity sha512-VSr8fXfI93obYaQicLJbLUKGRxDojj/SfRJDDLCioGTUBj4BK/Nj4eE9jCeCAnJxVLi7iS+08PbiZLyrQKBkJQ==):
swagger-ui-bundle.js, swagger-ui-bundle.js.LICENSE.txt and swagger-ui.css
unchanged, LICENSE and NOTICE as LICENSE.swagger-ui and NOTICE.swagger-ui.
To update, replace these files from the new package and update the version
here.
"""

import os

from sphinx.util.osutil import copyfile

here = os.path.abspath(os.path.dirname(__file__))
schema = os.path.join(here, '..', '..', 'open_api', 'schema.json')


def assets(app, exception):
    if exception:
        return
    static = os.path.join(app.outdir, '_static')
    for asset in os.listdir(here):
        if asset == '__pycache__' or asset.endswith(('.py', '.pyc')):
            continue
        copyfile(os.path.join(here, asset), os.path.join(static, asset))
    copyfile(schema, os.path.join(static, 'schema.json'))


def setup(app):
    if not os.path.exists(schema):
        raise FileNotFoundError(f'{schema} is missing; download it with docs/docsite/download-json.py')
    app.connect('build-finished', assets)
    return {'version': 2.0, 'parallel_read_safe': True}
