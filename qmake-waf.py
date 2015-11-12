import qmake
import os
from waflib.TaskGen import extension, feature
from waflib.Task import Task

class MocBuilder:
    def __init__(self,bld):
        self.bld = bld
        self.moc_headers = []
        self.mocs = []
        self.cxxflags = []

    def __call__(self,subproject):
        if subproject.qt:
            subproject.mocs = []
            for moc_source in subproject.headers:

                f = open(os.path.join( subproject.pwd, moc_source ), 'r')
                lines = f.read()
                q_object_line = lines.find('Q_OBJECT')
                if q_object_line >= 0:
                    basename = os.path.basename(moc_source) 
                    mocbase = 'moc_' + basename.split('.')[0] + '.cpp' 
                    tgt= os.path.join( subproject.target, mocbase )
                    src= os.path.join( subproject.target, moc_source )
                    subproject.mocs.append(mocbase)

                    self.bld( 
                            rule= '${QT_MOC} ${MOC_FLAGS} ${MOCCPPPATH_ST:INCPATHS} ${MOCDEFINES_ST:DEFINES} ${SRC} ${MOC_ST} ${TGT}',
                            source = src,
                            target = tgt 
                    )


class QmakeProjectBuilder:
    def __init__(self,bld):
        self.build_ctx = bld

    def __call__(self, subproject):
        project_features = ''

        subproject_includes = subproject.includes
        build_dir = os.path.join(self.build_ctx.bldnode.abspath(), subproject.target ) 
        subproject_includes.append( build_dir )
        subproject_use=subproject.dependencies
        if subproject.qt:
            project_features = 'qt5'
            subproject_use = subproject_use + subproject.qtmodules

        moc_sources = []

        if subproject.template=='lib':
            self.build_ctx.stlib(
                    source=' '.join([ os.path.join(subproject.target, s) for s in subproject.sources + getattr(subproject, 'mocs', []) ]),
                    target=subproject.target,
                    includes=subproject_includes,
                    cxxflags=subproject.cxxflags,
                    lib=subproject.libraries,
                    libpath=subproject.library_paths,
                    features = project_features,
                    use=subproject_use
            )
        elif subproject.template=='app':
            self.build_ctx.program(
                    source=' '.join([ os.path.join(subproject.target, s) for s in subproject.sources + getattr(subproject, 'mocs', []) ]),
                    target='bin/' + subproject.target,
                    includes=subproject_includes,
                    cxxflags=subproject.cxxflags,
                    use=subproject_use,
                    lib=subproject.libraries,
                    libpath=subproject.library_paths,
                    features = project_features,
            )

def options(opt):
    opt.load('compiler_cxx')

def qmake_configure(conf):
    conf.load('compiler_cxx qt5')
    conf.env['ui_PATTERN'] = "ui_%s.h"

def qmake_build(projectFile, bld):
    qproject = qmake.project('analytics.pro',qmake_executable=bld.env.QMAKE[0])

    @extension('.ui')
    def create_uic_task(self, node):
        "hook for uic tasks"
        uinode = node.change_ext('')
        dirname, basename = ( os.path.dirname(uinode.relpath()), os.path.basename(uinode.relpath()) )
        outputFilename = os.path.join( dirname, self.env['ui_PATTERN'] % basename )
        uictask = self.create_task('ui5', node)
        uictask.outputs = [self.path.find_or_declare( outputFilename )]

    @extension('.hpp')
    def create_hpp_task(self, node):
        "hook for hpp tasks"
        print node.relpath()

    qproject.foreach_project( MocBuilder(bld) )
    qproject.foreach_project( QmakeProjectBuilder(bld) )


