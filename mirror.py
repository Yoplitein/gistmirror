#!/usr/bin/env python3

import argparse
import datetime
import os
import re
import sys

import dulwich.porcelain
import requests

slugRe = re.compile(r"[^a-zA-Z0-9._-]")
auth = ()

def getGists(user, private):
    authDict = dict(auth=auth) if auth else {}
    url = "https://api.github.com/users/{}/gists".format(user)
    gists = []
    
    while url:
        response = requests.get(url, *authDict)
        link = response.headers.get("Link", "")
        rawGists = response.json()
        
        if response.status_code != 200:
            import json
            
            print(json.dumps(rawGists, indent="    "))
            
            return []
        
        if not link:
            url = ""
        else:
            links = {k: v for v, k in [[x.strip("<>\"") for x in pair.split("; rel=")] for pair in link.split(", ")]}
            url = links.get("next", "")
        
        for rawGist in rawGists:
            if not rawGist["public"] and not private:
                continue
            
            gist = {k: rawGist.get(k, "") for k in ["id", "git_pull_url", "created_at", "description"]}
            gist["files"] = list(rawGist["files"].keys())
            
            gists.append(gist)
    
    return gists

def branchName(gist, mode):
    id = gist["id"]
    description = gist["description"]
    files = [file for file in gist["files"] if not file.lower().startswith("gistfile")]
    
    if mode == "ctime":
        return slugRe.sub("_", gist["created_at"]).replace("T", "_").replace("Z", "")
    
    if mode == "description" and description != "":
        desc = description.strip()[:50].strip(".")
        
        return "{}_{}".format(
            slugRe
                .sub("_", desc)[:50]
                .lower()
            ,
            id[:10]
        )
    elif description == "":
        mode = "filename"
    
    if mode == "filename" and len(files) > 0:
        return "{}_{}".format(
            "_".join(slugRe.sub("_", file) for file in files),
            id[:10]
        )
    elif mode == "filename" and len(gist["files"]) > 0:
        extensions = "_".join(
            x for x in
            [os.path.splitext(file)[1][1:] for file in gist["files"]]
            if x != ""
        )
        
        if extensions != "":
            return "{}_{}".format(extensions, id[:10])
    
    return id

def main():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("-r", "--repo", required=True, help="Path to a bare repository that gists will be pulled to.")
    parser.add_argument("-u", "--user", required=True, help="User to mirror gists from.")
    parser.add_argument("-p", "--private", action="store_true", default=False, help="Whether to include private repositories.")
    parser.add_argument("-b", "--branch-names", choices=["hash", "ctime", "description", "filename"], default="hash")
    parser.add_argument("-U", "--token-user", default=None, help="When using authenticated requests, the username to authenticate as.")
    parser.add_argument("-t", "--token", default=None, type=argparse.FileType("r"), help="A file containing an API token. Enables authenticated requests.")
    
    parsed = parser.parse_args(sys.argv[1:])
    
    
    if parsed.token_user or parsed.token:
        if parsed.token_user is None or parsed.token is None:
            parser.error("Both --token and --token-user must be defined.")
        
        global auth
        
        with parsed.token as file:
            auth = (parsed.token_user, file.read().strip())
    
    repo = parsed.repo
    gists = getGists(parsed.user, parsed.private)
    
    for gist in gists:
        try:
            dulwich.porcelain.remote_add(repo, gist["id"], gist["git_pull_url"])
        except:
            pass
        
        branch = branchName(gist, parsed.branch_names)
        refs = dulwich.porcelain.fetch(repo, gist["git_pull_url"], gist["id"].encode("utf-8"))
        
        try:
            dulwich.porcelain.branch_delete(repo, branch)
        except:
            pass
        
        dulwich.porcelain.branch_create(repo, branch, refs[b"HEAD"].decode("utf-8"))

if __name__ == '__main__':
    main()
