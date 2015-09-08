#!/usr/bin/env python
    
# Python script to traverse GIT DAG backwards in time, tracing a branch
# through merges and emitting merge parents that are not the desired
# branch for the purpose of building a set of commits to pass to 
# 'git bisect good' so that we can use git bisect and omit all
# paths that are not part of the desired branch.

import re
import sys
import subprocess


def IsValidCommit(commit):
   sp = subprocess.Popen(["git","cat-file",'-e',commit+'^0'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   sp.wait()
   return sp.returncode == 0
   

def IsReachable(commit, fromCommit):
   sp = subprocess.Popen(["git","merge-base",'--is-ancestor',commit,fromCommit],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   sp.wait()
   return sp.returncode == 0
   
   
def GetParents(commit):
   sp = subprocess.Popen(["git","log",'--pretty="%p"','-1',commit],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   o1 = sp.communicate()[0]   
   o2 = str.replace(o1,'"','')   
   o3 = o2.split()
   return o3


def GetCommitComments(commit):
   sp = subprocess.Popen(["git","log",'--format="%B"','-1',commit],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   o1 = sp.communicate()[0]
   return o1.rstrip()
   

# Returns (parentOnSameBranch, otherParent)
p1 = re.compile("Merge branch '.+'")
p2 = re.compile("Merge remote-tracking branch '.+'")
p3 = re.compile("Merge commit '.+'")
def ParseMergeCommitCommentsForParentOnSameBranch(commit,branchName):
    cc = GetCommitComments(commit).replace('"','').split("\n")

    p = GetParents(commit)
    if len(p) == 1:
       sys.stderr.write("Internal error, on commit %s that I thought was a merge, but its only got one parent (so can't be a merge). Bailing\n" % commit)
       sys.exit(-1)
       
    if len(p) > 2:
       sys.stderr.write("ERROR - merge commit %s has more than two parents. Haven't updated code for octopus merges yet\n" % commit)
       sys.exit(-1)

    mergedInBranchName = None
    for c in cc:
       m = p1.search(c)
       if m is not None:
          firstQuote = c.index("'",m.start())
          secondQuote = c.index("'",firstQuote+1)
          mergedInBranchName = c[firstQuote+1:secondQuote]
          break
       m = p2.search(c)
       if m is not None:
          firstQuote = c.index("'",m.start())
          secondQuote = c.index("'",firstQuote+1)
          mergedInBranchName = c[firstQuote+1:secondQuote]
          break
       m = p3.search(c)
       if m is not None:
          firstQuote = c.index("'",m.start())
          secondQuote = c.index("'",firstQuote+1)
          mergedInBranchName = c[firstQuote+1:secondQuote]
          break
    
    if mergedInBranchName is None:
        sys.stderr.write("ERROR - cant figure out from commit comment which parent is the branch we are trying to follow. Bailing\n")
        sys.exit(-1)
        
    if branchName == mergedInBranchName:
        return (p[1],p[0])
    else:
        return (p[0],p[1])


def FollowParent(commit, branchName):
   parents = GetParents(commit)
   if len(parents) == 0:
      return None
   if len(parents) == 1:
      return (parents[0],None)
      
   # Ok, now we have a merge commit, so figure out its parent from the commit comments
   return ParseMergeCommitCommentsForParentOnSameBranch(commit,branchName)


if len(sys.argv) != 4:
    sys.stderr.write("Must be invoked with three parameters, the first is the starting commit and the second is the ancestor commit to iterate to and the third is the branchName of the starting commit to follow to the ancestor commit\n")
    sys.exit(-1)

startingCommit = sys.argv[1]
endingCommit   = sys.argv[2]
branchName     = sys.argv[3]

if not IsValidCommit(startingCommit):
    sys.stderr.write("Starting commit '%s' isn't a valid SHA1 for a commit\n" % startingCommit)
    sys.exit(-1)

if not IsValidCommit(endingCommit):
    sys.stderr.write("Ending commit '%s' isn't a valid SHA1 for a commit\n" % endingCommit)
    sys.exit(-1)
    
# TBD verify startingCommit is in branchName

if not IsReachable(endingCommit, startingCommit):
   sys.stderr.write("Ending commit '%s' is not reachable from starting commit '%s'\n" % (endingCommit, startingCommit))
   sys.exit(-1)


discardedMergeHead = set()
nextCommit = startingCommit

while nextCommit is not None and not nextCommit.startswith(endingCommit):
   parentCommit = FollowParent(nextCommit,branchName)
   if parentCommit[1] is not None:
      discardedMergeHead.add(parentCommit[1])
   print parentCommit[0]
   nextCommit = parentCommit[0]
   
print "Discarded heads:" 
print("".join(str(x)+' ' for x in discardedMergeHead))

