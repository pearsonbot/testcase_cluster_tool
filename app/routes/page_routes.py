from flask import Blueprint, render_template

bp = Blueprint('pages', __name__)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/settings')
def settings():
    return render_template('settings.html')


@bp.route('/clusters')
def clusters():
    return render_template('clusters.html')


@bp.route('/clusters/<int:cluster_id>')
def cluster_detail(cluster_id):
    return render_template('cluster_detail.html', cluster_id=cluster_id)
