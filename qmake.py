import sys
import re
import os
import shlex
import subprocess 
from collections import defaultdict

class matchers:
    lineContinuation = re.compile(r'(.*)\\\s*$')
    variableDefinition = re.compile(r'\s*(\w+)\s*(\+=|=)(.*)$')
    include = re.compile(r'\s*include\(\s*(\S+)\s*\)\s*$')

    qmake_function = re.compile(r'\$\$(\w+)(\(.*\))')
    qmake_variable_with_braces = re.compile(r'\$\$\{(.+)\}')
    qmake_variable_without_braces = re.compile(r'\$\$(\S+)')
    lib = re.compile('-l(\S+)')
    libpath = re.compile('-L\s*(\S+)')

    @staticmethod
    def processVariable( values, variables, print_actions ):
        if print_actions: print 'processing values: [', ','.join(values), ']'

        try:
            found_match = False

            for i,value in enumerate(values):
                qmake_functions = re.finditer(matchers.qmake_function,value)
                for qmake_function in qmake_functions:
                    values[i] = re.sub(matchers.qmake_function, '', values[i] )

                braces_matches = re.finditer(matchers.qmake_variable_with_braces,value)
                for braces_match in braces_matches:
                    if print_actions: print 'braces match'
                    varName = braces_match.group(1)
                    varVal = variables.get(varName)
                    if varVal:
                        org = values[i]
                        values[i] = re.sub(matchers.qmake_variable_with_braces, ''.join(varVal), values[i] )
                        if print_actions: print varName, org, " -> ", values[i]
                        found_match = True

                nobraces_matches = re.finditer( matchers.qmake_variable_without_braces, value)
                for nobraces_match in nobraces_matches:
                    if print_actions: print 'no braces match'
                    varName = nobraces_match.group(1)
                    varVal = variables.get(varName)
                    if varVal:
                        org = values[i]
                        values[i] = re.sub(matchers.qmake_variable_without_braces, ''.join(varVal), values[i] )
                        if print_actions: print varName, org, " -> ", values[i]
                        found_match = True
            
            return found_match
        except Exception as e:
            print 'caught exception while replacing variables in',str(values), ' exception: ', str(e)
            return False

def print_debug(level, line):
    if level == "debug":
        sys.stdout.write(line+'\n')

class project:
    def __init__(self,filename,parent=None,isInclude=False,debug_level="none",qmake_executable='/usr/bin/qmake'):
        self.parent = parent
        self.debug_level = debug_level
        self.pwd = os.path.dirname( os.path.abspath(filename) )
        self.abspwd = os.path.abspath(self.pwd)
        self.filename = os.path.basename(filename)
        self.qmake_includes = { } ## mostly irrelevant externally and internally
        self.variables = { }
        self.dependencies = []
        self.includes = []
        self.libraries = []
        self.library_paths = [ ]
        self.forms = []
        self.moc_headers = []
        self.moc_exec = 'moc'
        self.qt_include_dir= ''
        self.qt_bin_dir    = ''

        if not parent:
            qmake_query = [qmake_executable,'-query']
            query_install_headers = qmake_query + ['QT_INSTALL_HEADERS']
            query_install_bins    = qmake_query + ['QT_INSTALL_BINS']

            self.qt_include_dir= subprocess.check_output(query_install_headers)[:-1]
            self.qt_bin_dir    = subprocess.check_output(query_install_bins)[:-1]
            moc_exec = os.path.join( self.qt_bin_dir, 'moc' )
            if os.path.isfile( moc_exec ):
                self.moc_exec = moc_exec
        else:
            self.qt_include_dir= parent.qt_include_dir
            self.qt_bin_dir    = parent.qt_bin_dir
            self.moc_exec      = parent.moc_exec


        if isInclude:
            self.target=self.filename.split('.')[0]
        else:
            self.target=self.filename.split('.')[0]

        self.subprojects = None

        #if self.target == 'common':
        #    self.debug_level = "debug"

        ## Actual parsing here, after this line you can query variables, subprojects, includes, etc.
        self.parse(os.path.join(self.pwd,self.filename))

        template = self.variables.get('TEMPLATE')
        self.variables['TARGET']=[ self.target ]
        self.variables['_FILE_']=[ self.filename ]
        self.variables['PWD']=[ self.pwd ]

        self.process_variables()
        self.cxxflags = self.variables.get('QMAKE_CXXFLAGS',[])

        if template and not isInclude:
            dependencies=self.variables.get('DEPENDENCIES')
            if dependencies: self.dependencies += dependencies

            self.qt = self.variables.get('QT')
            self.template = template[0]
            if self.template == 'subdirs':
                self.subprojects = []
                subdirs = self.variables.get('SUBDIRS')
                if subdirs:
                    for subdir in subdirs:
                        subdirFile = os.path.join(subdir, subdir + '.pro' ) 
                        try:
                            self.subprojects.append( project( subdirFile ) )
                        except:
                            print "caught exception while parsing subproject: ", subdirFile
                            sys.exit(1)
            elif self.template == 'lib' or self.template == 'app':
                self.sources  = self.variables.get('SOURCES',[])
                self.headers  = self.variables.get('HEADERS',[])
                self.includes = self.variables.get('INCLUDEPATH',[])
                self.moc_headers = self.variables.get('MOC_HEADERS',[])

                self.libraries = [ matchers.lib.match(l).group(1) for l in self.variables.get('LIBS',[]) if matchers.lib.match(l) and matchers.lib.match(l).group(1) ]
                self.library_paths = [ matchers.libpath.match(l).group(1) for l in self.variables.get('LIBS',[]) if matchers.libpath.match(l) and matchers.libpath.match(l).group(1) ]

                if self.qt:
                    self.forms = self.variables.get('FORMS',[])
                    self.sources  = self.sources + self.forms
                    self.cxxflags.append('-fPIC')
                    try:
                        self.includes.append(self.qt_include_dir)  
                        self.qtmodules = []
                        self.qtlibraries = []
                        for qtmodule in self.qt:
                            fullModuleName = 'Qt' + qtmodule.title()
                            fullLibaryName = 'Qt5' + qtmodule.title()
                            self.qtmodules.append(fullModuleName)
                            self.qtlibraries.append(fullLibaryName)
                            self.libraries.append(fullLibaryName)
                            qtIncludes=os.path.join(self.qt_include_dir, fullModuleName)
                            self.includes.append(qtIncludes)
                    except Exception as e:
                        print 'exception while querying qmake:', str(e)

        
    def process_variables(self):
        for key, value in self.variables.iteritems():
            orig = ','.join(value)
            replacementsProcessed = False
            while matchers.processVariable(value,self.variables, self.debug_level == "debug" ): replacementsProcessed = True

            if replacementsProcessed:
                print_debug( self.debug_level, " processed replacements in " + key + " = " + ','.join(value) + ' <- ' + orig )

    def foreach_project(self, fun):
        fun(self) ## call self, then see if we have subprojects
        if self.subprojects:
            for subproject in self.subprojects:
                subproject.foreach_project(fun)

    def parse(self,projectFilename):
        try:
            projectFile = open(projectFilename)
            with projectFile:
                currentLine = ""
                lineCount=0
                for line in projectFile:
                    lineCount += 1
                    match = matchers.lineContinuation.match(line)
                    if match:
                        currentLine += match.group(1)
                    else:
                        currentLine += line[:-1]
                        self.parseLine(currentLine)
                        currentLine = ""

                if len(currentLine): ## currentLine was not parsed, probably
                    print "caught exception while parsing project: ", projectFilename
                    print "EOF with trailing line continuation", projectFilename, 'line:',lineCount
                    raise 

        except:
            print "caught exception while parsing project: ", projectFilename
            raise
            

    def parseLine(self, line):
        includeMatch = matchers.include.match(line) 
        if includeMatch:
            includeFile = includeMatch.group(1)
            absIncludeFile = os.path.join(self.abspwd, includeFile) 
            try:
                includeProject = project( absIncludeFile, self, True, self.debug_level )
                self.qmake_includes[ includeFile ] = includeProject 
                for key,values in includeProject.variables.iteritems():
                    self.variables[key] = self.variables.get(key,[]) + values
                    print_debug( self.debug_level, "imported " + key + " " + ','.join(values) + " from " + includeFile )
                return
            except:
                print "caught exception while parsing include: ", absIncludeFile, 'from:', self.filename
                raise

        varMatch = matchers.variableDefinition.match(line)
        if varMatch:
            variableName = varMatch.group(1)
            assignmentType = varMatch.group(2)
            values = shlex.split(varMatch.group(3))
            if assignmentType == "=":
                values = self.variables[variableName] = values
            elif assignmentType == "+=":
                self.variables[variableName] = self.variables.get(variableName,list()) + values

            return
            

