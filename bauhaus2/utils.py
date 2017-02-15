import os, stat, itertools, os.path as op




def mkdirp(path):
    try:
        os.makedirs(path)
    except OSError:
        # "path already exists", presumably... should verify
        pass

def chmodPlusX(path):
    originalStat = os.stat(path).st_mode
    os.chmod(path, originalStat | stat.S_IXUSR)

def listConcat(lsts):
    return list(itertools.chain(*lsts))

def readFile(path):
    return open(path).read()

def writeFile(path, content):
    with open(path, "w") as f:
        f.write(content)

def quote(s):
    return '"%s"' % s
    
    


## Test



#print includes("bauhaus2/workflows/map-subreads.snake")
##print chaseSnakemakeIncludes("bauhaus2/workflows/map-subreads.snake")