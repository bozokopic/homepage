from pathlib import Path
import collections
import functools
import multiprocessing
import os
import shutil
import subprocess

from hat import json
import docutils.core
import docutils.io
import lxml.html
import mako.lookup
import mako.template


num_process = int(os.environ.get('DOIT_NUM_PROCESS',
                                 multiprocessing.cpu_count()))

DOIT_CONFIG = {'backend': 'sqlite3',
               'default_tasks': ['build'],
               'verbosity': 2,
               'num_process': num_process}

build_dir = Path('build')
src_html_dir = Path('src_html')
src_rst_dir = Path('src_rst')
src_scss_dir = Path('src_scss')
src_static_dir = Path('src_static')

rst_tmpl_path = src_html_dir / '_rst.html'
feed_path = build_dir / 'index.xml'

conf = json.decode_file(Path('conf.yaml'))


def task_clean_all():
    """Clean all"""
    return {'actions': [functools.partial(shutil.rmtree, str(build_dir),
                                          ignore_errors=True)]}


def task_build():
    """Build"""
    return {'actions': None,
            'task_dep': ['pages',
                         'feed',
                         'sass',
                         'static']}


def task_pages():
    """Build pages"""
    for entry in conf['entries']:
        src_path = Path(entry['src'])
        dst_path = (build_dir / src_path).with_suffix('.html')
        depth = len(dst_path.relative_to(build_dir).parents) - 1
        root_prefix = '../' * depth
        params = {'conf': conf,
                  'entry': entry,
                  'root_prefix': root_prefix}

        if src_path.suffix == '.html':
            src_path = src_html_dir / src_path
            action_fn = _build_mako

        elif src_path.suffix == '.rst':
            src_path = src_rst_dir / src_path
            action_fn = _build_rst

        else:
            raise Exception('unsupported entry source')

        yield {'name': str(dst_path),
               'actions': [(action_fn, [src_path, dst_path, params])],
               'targets': [dst_path]}


def task_feed():
    """Build feed"""
    return {'actions': [_build_feed],
            'task_dep': ['pages']}


def task_sass():
    """Build sass"""
    for src_path, dst_path in _get_scss_mappings():
        yield {'name': str(dst_path),
               'actions': [(_build_scss, [src_path, dst_path])],
               'targets': [dst_path],
               'task_dep': ['deps']}


def task_static():
    """Copy static files"""
    for src_path, dst_path in _get_static_mappings():
        yield {'name': str(dst_path),
               'actions': [functools.partial(dst_path.parent.mkdir,
                                             parents=True, exist_ok=True),
                           functools.partial(shutil.copy2,
                                             str(src_path), str(dst_path))],
               'targets': [dst_path]}


def task_deps():
    """Install dependencies"""
    return {'actions': ['yarn install --silent']}


def _build_mako(src_path, dst_path, params):
    tmpl_lookup = mako.lookup.TemplateLookup(directories=[str(src_html_dir)],
                                             input_encoding='utf-8')
    tmpl_uri = tmpl_lookup.filename_to_uri(str(src_path))
    tmpl = tmpl_lookup.get_template(tmpl_uri)
    output = tmpl.render(**params)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(output)


def _build_rst(src_path, dst_path, params):
    _, pub = docutils.core.publish_programmatically(
        source_class=docutils.io.StringInput,
        source=src_path.read_text(),
        source_path=None,
        destination_class=docutils.io.StringOutput,
        destination=None,
        destination_path=None,
        reader=None,
        reader_name='standalone',
        parser=None,
        parser_name='restructuredtext',
        writer=None,
        writer_name='html5',
        settings=None,
        settings_spec=None,
        settings_overrides=None,
        config_section=None,
        enable_exit_status=False)
    body = pub.writer.parts['html_body']

    _build_mako(src_path=rst_tmpl_path,
                dst_path=dst_path,
                params={'body': body,
                        **params})


def _build_feed():
    updated = ""
    entries = collections.deque()

    for i in conf['entries']:
        if 'published' not in i:
            continue

        src_path = (build_dir / i["src"]).with_suffix('.html')
        link = str(src_path.relative_to(build_dir))
        root = lxml.html.fromstring(src_path.read_text())
        content = lxml.html.tostring(root.xpath('/html/body/main')[0],
                                     encoding='utf-8',
                                     method='xml').decode('utf-8')

        if i['published'] > updated:
            updated = i['published']
        if 'updated' in i and i['updated'] > updated:
            updated = i['updated']

        entry = (f'<entry>\n'
                 f'<title>{i["title"]}</title>\n'
                 f'<link href="{conf["link"]}/{link}"/>\n'
                 f'<id>urn:uuid:{i["id"]}</id>\n'
                 f'<published>{i["published"]}</published>\n')
        if 'updated' in i:
            entry += f'<updated>{i["updated"]}</updated>\n'
        entry += f'<content type="xhtml">\n{content}\n</content>\n'
        entry += '</entry>\n'

        entries.append(entry)

    feed_path.write_text(f'<?xml version="1.0" encoding="utf-8"?>\n'
                         f'<feed xmlns="http://www.w3.org/2005/Atom">\n'
                         f'<title>Bozo Kopic home page</title>\n'
                         f'<link href="{conf["link"]}"/>\n'
                         f'<link href="{feed_path.name}" rel="self"/>\n'
                         f'<id>urn:uuid:{conf["id"]}</id>\n'
                         f'<updated>{updated}</updated>\n'
                         f'<author>\n'
                         f'<name>{conf["author"]["name"]}</name>\n'
                         f'<email>{conf["author"]["email"]}</email>\n'
                         f'</author>\n'
                         f'{"".join(entries)}'
                         f'</feed>\n')


def _build_scss(src_path, dst_path):
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['node_modules/.bin/sass', '--no-source-map',
                    str(src_path), str(dst_path)],
                   check=True)


def _get_scss_mappings():
    for src_path in src_scss_dir.rglob('*.scss'):
        if src_path.name.startswith('_'):
            continue
        dst_path = (build_dir /
                    src_path.relative_to(src_scss_dir).with_suffix('.css'))
        yield src_path, dst_path


def _get_static_mappings():
    for src_path in src_static_dir.rglob('*'):
        if src_path.is_dir():
            continue
        dst_path = build_dir / src_path.relative_to(src_static_dir)
        yield src_path, dst_path
