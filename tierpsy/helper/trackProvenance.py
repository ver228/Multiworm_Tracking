import os
import json
import tables
import git


def getVersion(main_package):
    git_file = os.path.join(
        (os.sep).join(
            (main_package.__file__).split(
                os.sep)[
                0:-2]),
        '.git')
    try:
        repo = git.Repo(git_file)
        return repo.commit('HEAD').hexsha
    except git.exc.NoSuchPathError:
        return main_package.__version__


def getGitCommitHash():
    import MWTracker
    import open_worm_analysis_toolbox

    commits_hash = {
        'MWTracker': getVersion(MWTracker),
        'open_worm_analysis_toolbox': getVersion(open_worm_analysis_toolbox)}

    return commits_hash


def execThisPoint(
        thisPoint,
        func,
        argkws,
        provenance_file,
        commit_hash,
        cmd_original):
    # execute the function
    func(**argkws)

    # make sure the file was created correctly
    assert os.path.exists(provenance_file)

    # this are the variables that are going to be stored
    variables2save = {
        'func_name': func.__name__,
        'func_arguments': json.dumps(argkws),
        'commit_hash': commit_hash,
        'cmd_original': cmd_original}
    variables2save = bytes(json.dumps(variables2save), 'utf-8')

    # store the variables in the correct node
    with tables.File(provenance_file, 'r+') as fid:
        main_node = 'provenance_tracking'
        if not '/' + main_node in fid:
            fid.create_group('/', main_node)
        if '/'.join(['', main_node, thisPoint]) in fid:
            fid.remove_node('/' + main_node, thisPoint)

        fid.create_array('/' + main_node, thisPoint, obj=variables2save)
        fid.flush()
