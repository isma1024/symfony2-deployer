from fabric.api import *
from fabric.utils import abort, puts
from fabric.colors import green, red, yellow
from fabric.state import output
import os
import re
import yaml

"""
Set global data before functions
"""

# Set config file that will be used
config_file = 'app/config/hosts.yml'

# Import and parse config file
if not os.path.isfile(config_file):
    abort(red('Config file %s does not exist' % config_file, bold=True))

with open(config_file, 'r') as stream:
    hosts = yaml.load(stream)

# Check that requested server exists
if env.server not in hosts['hosts']:
    abort(red('Server %s does not exist in configuration file' % env.server, bold=True))

# Set server variable as global, as we will use it in all functions
server = hosts['hosts'][env.server]

# Set Fabric env.hosts from the server variable we just defined
env.hosts = server['hosts']

# Forward agent if specified
env.forward_agent = server['forward_agent']

# Set False for required channels
if 'verbose' not in env.keys():
    output.stdout = False
    output.stderr = False
    output.running = False
    output.warnings = False


def pre_deploy():
    """
    Checkouts the specified branch and execute the tests, if specified.
    """
    _checkout()
    if server['tests']:
        _tests()


def deploy():
    """
    Deploys the application by updating the source to the last commit of the specified
    git branch, executes a composer update, installs assets (if specified) executes database
    migrations (if specified) and clears the cache.
    """

    with cd(server['path']):
        # Execute git pull
        _pull()

        # Execute post deployment tasks
        _post_deployment_tasks()

        _print_output('\nCorrectly deployed to %s' % env.server, '\n', False)


def rollback(revision='1'):
    """
    Deploys the application by updating the source to the last commit of the specified
    git branch, executes a composer update, executes database migrations (if specified)
    and clears the cache.
    :param revision: if it is a number, it rollbacks N commits back from last one; if it is a string, it rollbacks
    to that commit.
    """

    with cd(server['path']):
        # Pull, so we have all commits
        _pull()

        # Rollback according to version or a number of revisions
        revision = _do_rollback(revision)

        # Execute post deployment tasks
        _post_deployment_tasks()

        # Print okay and warning message, informing that the database may be not up to date
        _print_output('\nCorrectly rolled back to %s' % revision, '\n', False)
        print(yellow('Remember to check your database, because it may not be in sync with your code!!', bold=True))


def _checkout():
    """
    Checkouts specified branch.
    """
    _print_output('Locally checking out')

    local('git fetch')
    local('git checkout %s' % server['branch'])
    local('git pull origin %s' % server['branch'])

    _print_ok()


def _tests():
    """
    Executes tests.
    """
    _print_output('Executing tests')
    local('%s -c app' % server['phpunit_bin'])
    _print_ok()


def _pull():
    """
    Executing regular git pull, updating code to last commit.
    """
    _print_output('Updating source code')

    run('git fetch')
    run('git checkout %s' % server['branch'])
    run('git pull origin %s' % server['branch'])

    _print_ok()


def _do_rollback(revision):
    """
    Rollback according to version or a number of revisions
    :param revision: version or number of revisions to rollback
    :return:
    """
    _print_output('Rolling back')

    if re.match(r"\d+$", revision) is not None:
        run('git checkout HEAD~%s' % revision)
        revision = run('git rev-parse --short HEAD', quiet=True)
    else:
        result = run('git checkout %s' % revision, quiet=True)
        if result.failed:
            abort(red('Revision %s does not exist' % revision, bold=True))

    _print_ok()

    return revision


def _post_deployment_tasks():
    """
    Executes a composer update, installs assets (if specified), executes database migrations (if specified)
    and clears the cache.
    """
    _composer_update()
    _assets_install()
    _database_migrations()
    _cache_clear()


def _composer_update():
    """
    Composer update
    """
    _print_output('Updating composer')
    run('%s %s update' % (server['php_bin'], server['composer_bin']))
    _print_ok()


def _assets_install():
    """
    Assets install, if enabled
    """
    if 'assets' in server and server['assets']['enabled']:
        _print_output('Installing assets')

        assets_args = []

        if 'target_path' in server['assets'] and server['assets']['target_path']:
            assets_args.append(server['assets']['target_path'])

        if 'symlink' in server['assets'] and server['assets']['symlink']:
            assets_args.append('--symlink')

        if 'relative' in server['assets'] and server['assets']['relative']:
            assets_args.append('--relative')

        run('%s %s/app/console assets:install --env=prod %s' % (
            server['php_bin'], server['path'], ' '.join(assets_args)))

        _print_ok()


def _database_migrations():
    """
    Database migrations, if enabled
    """
    if 'database_migrations' in server and server['database_migrations']:
        _print_output('Migrating database')
        run('%s %s/app/console doctrine:migrations:migrate --env=prod --no-interaction' % (
            server['php_bin'], server['path']))
        _print_ok()


def _cache_clear():
    """
    Cache clear
    """
    _print_output('Clearing cache')
    run('%s %s/app/console cache:clear --env=prod' % (server['php_bin'], server['path']))
    _print_ok()


def _print_output(message, end='', padding=True):
    """
    Aux function for printing messages if verbose is not enabled
    :param message: the message to print
    :param end: the character to print at line end
    :return:
    """
    if 'verbose' not in env.keys():
        if padding:
            puts(green('{:.<100}'.format(message), bold=True), end=end, show_prefix=False, flush=True)
        else:
            puts(green(message, bold=True), end=end, show_prefix=False, flush=True)


def _print_ok():
    """
    Aux function for printing a tick
    :return:
    """
    _print_output(u'\u2714', '\n', False)
