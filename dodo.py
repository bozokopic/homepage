from pathlib import Path
import subprocess

import docutils.core
import docutils.io
import mako.lookup
import mako.template

from hat import json
from hat.doit import common


DOIT_CONFIG = common.init(default_tasks=['build'])

build_dir = Path('build')
src_html_dir = Path('src_html')
src_rst_dir = Path('src_rst')
src_scss_dir = Path('src_scss')
src_static_dir = Path('src_static')

article_tmpl_path = src_html_dir / '_article.html'
feed_path = build_dir / 'index.xml'

conf = json.decode_file(Path('conf.yaml'))


def task_clean_all():
    """Clean all"""
    return {'actions': [(common.rm_rf, [build_dir])]}


def task_build():
    """Build"""
    return {'actions': None,
            'task_dep': ['pages',
                         'articles',
                         'feed',
                         'sass',
                         'static']}


def task_pages():
    """Build pages"""
    for page in conf['pages']:
        dst_path = _get_page_dst_path(page)

        yield {'name': str(dst_path),
               'actions': [(_build_page, [page])],
               'targets': [dst_path]}


def task_articles():
    """Build articles"""
    for article in conf['articles']:
        dst_path = _get_article_dst_path(article)

        yield {'name': str(dst_path),
               'actions': [(_build_article, [article])],
               'targets': [dst_path]}


def task_feed():
    """Build feed"""
    return {'actions': [_build_feed],
            'task_dep': ['pages']}


def task_sass():
    """Build sass"""
    for src_path in src_scss_dir.rglob('*.scss'):
        if src_path.name.startswith('_'):
            continue

        dst_path = (build_dir /
                    src_path.relative_to(src_scss_dir).with_suffix('.css'))

        yield {'name': str(dst_path),
               'actions': [(_build_scss, [src_path, dst_path])],
               'targets': [dst_path],
               'task_dep': ['node_modules']}


def task_static():
    """Copy static files"""
    for src_path in src_static_dir.rglob('*'):
        if src_path.is_dir():
            continue

        dst_path = build_dir / src_path.relative_to(src_static_dir)

        yield {'name': str(dst_path),
               'actions': [(common.mkdir_p, [dst_path.parent]),
                           (common.cp_r, [src_path, dst_path])],
               'targets': [dst_path]}


def task_node_modules():
    """Install node_modules"""
    return {'actions': ['yarn install --silent']}


def _build_page(page):
    src_path = src_html_dir / page['src']
    dst_path = _get_page_dst_path(page)

    params = {'conf': conf,
              'title': page['title'],
              'root_prefix': '../' * _get_path_depth(build_dir, dst_path)}

    _build_mako(src_path=src_path,
                dst_path=dst_path,
                params=params)


def _build_article(article):
    src_path = src_rst_dir / article['src']
    dst_path = _get_article_dst_path(article)

    params = {'conf': conf,
              'title': article['title'],
              'root_prefix': '../' * _get_path_depth(build_dir, dst_path),
              'published': article.get('published'),
              'updated': article.get('updated'),
              'body': _build_rst(src_path, 'long')}

    _build_mako(src_path=article_tmpl_path,
                dst_path=dst_path,
                params=params)


def _build_feed():
    updated = max((article.get(key, '')
                   for article in conf['articles']
                   for key in ('published', 'updated')),
                  default='')

    with open(feed_path, 'w', encoding='utf-8') as f:
        f.write(f'<?xml version="1.0" encoding="utf-8"?>\n'
                f'<feed xmlns="http://www.w3.org/2005/Atom">\n'
                f'<title>Bozo Kopic home page</title>\n'
                f'<link href="{conf["link"]}"/>\n'
                f'<link href="{feed_path.name}" rel="self"/>\n'
                f'<id>urn:uuid:{conf["id"]}</id>\n'
                f'<updated>{updated}</updated>\n'
                f'<author>\n'
                f'<name>{conf["author"]["name"]}</name>\n'
                f'<email>{conf["author"]["email"]}</email>\n'
                f'</author>\n')

        for article in conf['articles']:
            link = _get_article_dst_path(article).relative_to(build_dir)
            content = _build_rst(src_rst_dir / article['src'], 'none')

            f.write(f'<entry>\n'
                    f'<title>{article["title"]}</title>\n'
                    f'<link href="{conf["link"]}/{link}"/>\n'
                    f'<id>urn:uuid:{article["id"]}</id>\n'
                    f'<published>{article["published"]}</published>\n')
            if 'updated' in article:
                f.write(f'<updated>{article["updated"]}</updated>\n')
            f.write(f'<content type="xhtml">\n{content}\n</content>\n'
                    f'</entry>\n')

        f.write('</feed>\n')


def _build_scss(src_path, dst_path):
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['node_modules/.bin/sass', '--no-source-map',
                    str(src_path), str(dst_path)],
                   check=True)


def _build_mako(src_path, dst_path, params):
    tmpl_lookup = mako.lookup.TemplateLookup(directories=[str(src_html_dir)],
                                             input_encoding='utf-8')
    tmpl_uri = tmpl_lookup.filename_to_uri(str(src_path))
    tmpl = tmpl_lookup.get_template(tmpl_uri)
    output = tmpl.render(**params)

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(output)


def _build_rst(src_path, syntax_highlight):
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
        writer_name='html5_polyglot',
        settings=None,
        settings_spec=None,
        settings_overrides={'math_output': 'MathML',
                            'syntax_highlight': syntax_highlight},
        config_section=None,
        enable_exit_status=False)

    return pub.writer.parts['html_body']


def _get_page_dst_path(page):
    return build_dir / page['src']


def _get_article_dst_path(article):
    return (build_dir / 'articles' / article['src']).with_suffix('.html')


def _get_path_depth(parent_dir, path):
    return len(path.relative_to(parent_dir).parents) - 1
