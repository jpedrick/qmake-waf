import qmakeWaf

def options(opt):
    qmakeWaf.qmake_options(opt)

def configure(conf):
    qmakeWaf.qmake_configure(conf)

def build(bld):
    qmakeWaf.qmake_build('myproject.pro',bld)

