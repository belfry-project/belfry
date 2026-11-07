"""The OpenAPI schema explorer page (open_api/explorer.html).

The page renders Belfry's OpenAPI 3 schema with Redoc. It reads
_static/schema.json, which the swagger extension (rest_api/_swagger) copies
from rst/open_api/schema.json.

Redoc is vendored from the npm package redoc 2.5.4
(https://registry.npmjs.org/redoc/-/redoc-2.5.4.tgz,
integrity sha512-M6jWhG1qoBnH6TFmzJnstyCZ87HmOY/UzDm78mHiYihEdlV/YcS9ogOo1NlElnJMeLsyxHFe2yFc4sNjHTrABQ==):
bundles/redoc.standalone.js and bundles/redoc.standalone.js.LICENSE.txt
unchanged, LICENSE as LICENSE.redoc. To update, replace these files from the
new package and update the version here.
"""

import os

from sphinx.util.osutil import copyfile, ensuredir

here = os.path.abspath(os.path.dirname(__file__))


def assets(app, exception):
    if exception:
        return
    static = os.path.join(app.outdir, '_static')
    for asset in ('redoc.standalone.js', 'redoc.standalone.js.LICENSE.txt', 'LICENSE.redoc'):
        copyfile(os.path.join(here, asset), os.path.join(static, asset))
    page = os.path.join(app.outdir, 'open_api')
    ensuredir(page)
    copyfile(os.path.join(here, 'explorer.html'), os.path.join(page, 'explorer.html'))


def setup(app):
    app.connect('build-finished', assets)
    return {'version': 1.0, 'parallel_read_safe': True}
