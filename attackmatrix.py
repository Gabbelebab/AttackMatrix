#!/usr/bin/env python3

#
# (c) 2021 Arnim Eijkhoudt (arnime <thingamajic> kpn-cert.nl), GPLv3
#
# Please note: the MITRE ATT&CK® framework  is a registered trademark
# of MITRE. See https://attack.mitre.org/ for more information.
#
# I would like to thank MITRE for the permissive licence under which
# ATT&CK® is available.
#

import argparse
import dpath.util
import logging
import json
import pathlib
import pickle
import pprint
import shutil
import string
import urllib.request
import uvicorn
from config import settings as options
from config.matrixtable import Matrices
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse, RedirectResponse
from typing import List, Optional


tags_metadata = [
    {
        'name': 'docs',
        'description': 'This documentation.',
    },
    {
        'name': 'explore',
        'description': 'Basic interface for exploring the loaded MITRE ATT&CK® matrices. Returns a raw view of everything '
                       'under *treepath*, including all empty branches. **WARNING**: Can result in a lot of output!'
                       '<br /><br />'
                       '[Example query]'
                       '(http://' + options.ip + ':' + str(options.port) + '/api/explore/Enterprise/Actors/G0005)'
                       ' to find the *Actor G0005* in the *Enterprise* ATT&CK® matrix.',
    },
    {
        'name': 'search',
        'description': 'Does a case-insensitive *LOGICAL OR* (merge) search for all params fields in all entity names and '
                       'descriptions, and returns a list of matching entities. An optional *matrix* argument can be supplied '
                       'to limit searches to a particular ATT&CK® matrix.'
                       '<br /><br />'
                       '[Example query]'
                       '(http://' + options.ip + ':' + str(options.port) +
                       '/api/search?params=dragon&params=capture&params=property&matrix=ICS&matrix=Enterprise)'
                       ' to find all entities with the words *dragon*, *capture* or *property* in the Enterprise and '
                       'ICS ATT&CK® matrices.',
    },
    {
        'name': 'actoroverlap',
        'description': 'Finds the overlapping TTPs (*Malwares, Mitigations, Subtechniques, Techniques and Tools*) for '
                       'two actors. Returns a list of Actors, a list of matrices they were found in, and only the TTPs '
                       'that overlapped (with their names/descriptions).'
                       '<br /><br />'
                       '[Example query]'
                       '(http://' + options.ip + ':' + str(options.port) + '/api/actoroverlap/?actor1=G0064&actor2=G0050)'
                       ' to find the overlapping TTPs of *Actors G0064* and *G0050*.',
    },
    {
        'name': 'ttpoverlap',
        'description': 'Finds all actors that have a specific set of TTPs (*Malwares, Subtechniques, Techniques '
                       'and Tools*). The number of TTPs can be varied, i.e.: 1 ... n fields can be given. Returns '
                       'the matching Actors with all of their ATT&CK® entity types (including names/descriptions).'
                       '<br /><br />'
                       '[Example query]'
                       '(http://' + options.ip + ':' + str(options.port) + '/api/ttpoverlap/?ttp=S0002&ttp=S0008&ttp=T1560.001)'
                       ' to find which *Actors* use *Tool S0002*, *Tool S0008* and *Subtechnique T1560.001*.',
    },
    {
        'name': 'deprecated',
        'description': 'These functions are *DEPRECATED* and should only be used for compatibility reasons.',
    },
]
app = FastAPI(title='MITRE ATT&CK Matrix API', openapi_tags=tags_metadata)


@app.get('/', tags=['docs'])
async def read_root():
    return RedirectResponse('/docs')


@app.get('/api/', tags=['docs'])
async def read_api():
    return RedirectResponse('/docs')


@app.get('/api/explore/{treepath:path}', tags=['explore'])
async def query(request: Request,
                token: Optional[str] = None):
    if options.token:
        if token != options.token:
            raise HTTPException(status_code=403, detail='Missing or incorrect token')
    try:
        if not request.path_params['treepath']:
            return dpath.util.get(Matrices, '/')
        else:
            cache = loadCaches(options)
            return JSONResponse(dpath.util.get(cache, request.path_params['treepath'].strip('/'), separator='/'))
    except KeyError:
        return JSONResponse(content=json.dumps(None))


@app.get('/api/search/', tags=['search'])
async def searchParam(request: Request,
                      params: list = Query([]),
                      matrix: Optional[list] = Query(['ALL']),
                      token: Optional[str] = None):
    if options.token:
        if token != options.token:
            raise HTTPException(status_code=403, detail='Missing or incorrect token')
    if not (params or matrix):
        return {}
    else:
        return search(options, params, matrix)


@app.get('/api/search/{params:path}', tags=['deprecated'])
async def deprecatedSearch(request: Request,
                           params: str,
                           matrix: Optional[list] = Query(['ALL']),
                           token: Optional[str] = None):
    if options.token:
        if token != options.token:
            raise HTTPException(status_code=403, detail='Missing or incorrect token')
    if not (params or matrix):
        return {}
    else:
        params = request.path_params['params'].rstrip('/').split('/')
        return search(options, params, matrix)


@app.get('/api/actoroverlap/{mitreID1}/{mitreID2}', tags=['deprecated'])
async def deprecatedActorOverlap(request: Request,
                                 mitreID1: str,
                                 mitreID2: str,
                                 token: Optional[str] = None):
    if options.token:
        if token != options.token:
            raise HTTPException(status_code=403, detail='Missing or incorrect token')
    return findActorOverlap(options, mitreID1.rstrip('/'), mitreID2.rstrip('/'))


@app.get('/api/actoroverlap/', tags=['actoroverlap'])
async def actorOverlap(request: Request,
                       actor1: str,
                       actor2: str,
                       token: Optional[str] = None):
    if options.token:
        if token != options.token:
            raise HTTPException(status_code=403, detail='Missing or incorrect token')
    return findActorOverlap(options, actor1, actor2)


@app.get('/api/ttpoverlap/', tags=['ttpoverlap'])
async def ttpOverlap(request: Request,
                     ttp: list = Query([]),
                     token: Optional[str] = None):
    if options.token:
        if token != options.token:
            raise HTTPException(status_code=403, detail='Missing or incorrect token')
    return findTTPOverlap(options, ttp)


@app.get('/api/ttpoverlap/{ttp:path}', tags=['deprecated'])
async def deprecatedTTPOverlap(request: Request,
                               ttp: str,
                               token: Optional[str] = None):
    if options.token:
        if token != options.token:
            raise HTTPException(status_code=403, detail='Missing or incorrect token')
    TTPs = request.path_params['ttp'].rstrip('/').split('/')
    return findTTPOverlap(options, TTPs)


def findActorOverlap(options, mitreID1, mitreID2):
    actor1, actor2 = {}, {}
    cache = loadCaches(options)
    for matrixname in cache.keys():
        if options.verbose:
            logging.info('Searching ' + matrixname + ' for ' + mitreID1 + ' and ' + mitreID2)
        if cache[matrixname]['Actors'].get(mitreID1.rstrip('/')):
            actor1 = {**actor1, **{matrixname: {'Actors': cache[matrixname]['Actors'][mitreID1]}}}
        if cache[matrixname]['Actors'].get(mitreID2.rstrip('/')):
            actor2 = {**actor2, **{matrixname: {'Actors': cache[matrixname]['Actors'][mitreID2]}}}
    overlapkeys = {
        'Malwares': {},
        'Mitigations': {},
        'Subtechniques': {},
        'Techniques': {},
        'Tools': {},
    }
    overlap = {
        'Actors': {
            mitreID1: {
                'name': [],
                'description': '',
            },
            mitreID2: {
                'name': [],
                'description': '',
            },
        },
        'Malwares': {},
        'Matrices': {},
        'Mitigations': {},
        'Subtechniques': {},
        'Techniques': {},
        'Tools': {},
    }
    # Pivot the matrix names into a single list
    overlap['Matrices'] = {
        'name': set(list(actor1.keys())).union(set(list(actor2.keys()))),
        'description': 'List of ATT&CK® matrices in which the actors have been found',
    }
    actor1map = {
        'Malwares': {},
        'Mitigations': {},
        'Subtechniques': {},
        'Techniques': {},
        'Tools': {},
    }
    actor2map = {
        'Malwares': {},
        'Mitigations': {},
        'Subtechniques': {},
        'Techniques': {},
        'Tools': {},
    }
    for matrixname in overlap['Matrices']['name']:
        if actor1.get(matrixname):
            for overlapkey in overlapkeys.keys():
                if actor1[matrixname]['Actors'].get(overlapkey):
                    for entry in actor1[matrixname]['Actors'][overlapkey]:
                        if not entry in actor1map[overlapkey]:
                            actor1map[overlapkey][entry] = {}
            for name in actor1[matrixname]['Actors']['name']:
                overlap['Actors'][mitreID1]['name'].append(name)
            if actor1[matrixname]['Actors']['description'] not in overlap['Actors'][mitreID1]['description']:
                overlap['Actors'][mitreID1]['description'] += actor1[matrixname]['Actors']['description'].strip()+' '
        if actor2.get(matrixname):
            for overlapkey in overlapkeys.keys():
                if actor2[matrixname]['Actors'].get(overlapkey):
                    for entry in actor2[matrixname]['Actors'][overlapkey]:
                        if not entry in actor2map[overlapkey]:
                            actor2map[overlapkey][entry] = {}
            for name in actor2[matrixname]['Actors']['name']:
                overlap['Actors'][mitreID2]['name'].append(name)
            if actor2[matrixname]['Actors']['description'] not in overlap['Actors'][mitreID2]['description']:
                overlap['Actors'][mitreID2]['description'] += actor2[matrixname]['Actors']['description'].strip()+' '
    for overlapkey in overlapkeys.keys():
        overlap[overlapkey] = [entry for entry in actor1map[overlapkey] if entry in actor2map[overlapkey]]
        if len(overlap[overlapkey]) == 0:
            del overlap[overlapkey]
        else:
            keys = overlap[overlapkey]
            del overlap[overlapkey]
            overlap[overlapkey] = {}
            for key in keys:
                for matrixname in cache.keys():
                    if cache[matrixname][overlapkey].get(key):
                        overlap[overlapkey][key] = {
                            'name': cache[matrixname][overlapkey][key]['name'],
                            'description': cache[matrixname][overlapkey][key]['description'],
                        }
    overlap['Actors'][mitreID1]['description'] = overlap['Actors'][mitreID1]['description'].strip()
    overlap['Actors'][mitreID1]['name'] = list(set(overlap['Actors'][mitreID1]['name']))
    overlap['Actors'][mitreID2]['description'] = overlap['Actors'][mitreID2]['description'].strip()
    overlap['Actors'][mitreID2]['name'] = list(set(overlap['Actors'][mitreID2]['name']))
    if (overlapkeys.keys() & overlap.keys()):
        return overlap
    else:
        return


def findTTPOverlap(options, TTPs=[]):
    overlapkeys = {
        'Malwares': {},
        'Subtechniques': {},
        'Techniques': {},
        'Tools': {},
    }
    results = {}
    cache = loadCaches(options)
    for matrixname in cache.keys():
        results[matrixname] = {'Actors': {}}
        for candidate in cache[matrixname]['Actors'].keys():
            candidatecontent = []
            for overlapkey in overlapkeys:
                if cache[matrixname]['Actors'][candidate].get(overlapkey):
                    candidatecontent += cache[matrixname]['Actors'][candidate][overlapkey]
            if (len(candidatecontent) > 0) and all(ttp in candidatecontent for ttp in TTPs):
                results[matrixname]['Actors'][candidate] = cache[matrixname]['Actors'][candidate]
            for actor in results[matrixname]['Actors']:
                for ttpkey in overlapkeys.keys():
                    if results[matrixname]['Actors'][actor].get(ttpkey):
                        ttps = results[matrixname]['Actors'][actor][ttpkey]
                        del results[matrixname]['Actors'][actor][ttpkey]
                        results[matrixname]['Actors'][actor][ttpkey] = {}
                        for ttp in ttps:
                            if cache[matrixname][ttpkey].get(ttp):
                                results[matrixname]['Actors'][actor][ttpkey][ttp] = {
                                    'name': cache[matrixname][ttpkey][ttp]['name'],
                                    'description': cache[matrixname][ttpkey][ttp]['description'],
                                }
    for matrixname in cache.keys():
        if len(results[matrixname]['Actors'].keys()) == 0:
            del results[matrixname]
    return results


def loadCache(options, matrixname):
    cachefile = pathlib.Path(options.cachedir+'/'+matrixname+options.cacheaffix)
    if options.verbose:
        logging.info('Loading cache ' + cachefile.name + '...')
    try:
        with open(cachefile, 'rb') as cache:
            matrix = pickle.load(cache)
            return matrix
    except (ValueError, FileNotFoundError):
        if options.verbose:
            logging.error('Error loading the cachefile ' + cachefile.name)


def loadCaches(options):
    matrixcaches = list(Matrices.keys())
    matrices = {}
    for matrixname in matrixcaches:
        matrices = {**matrices, **loadCache(options, matrixname)}
    return matrices


def search(options, params=[], matrices='ALL'):
    if matrices == ['ALL']:
        matrices = Matrices.keys()
    else:
        if not isinstance(matrices, list):
            matrices = [matrices,]
    results = {}
    for matrixname in matrices:
        results[matrixname] = {}
        results[matrixname] = {**results[matrixname], **searchMatrix(options, params, matrixname)}
    return {key: value for key, value in results.items() if (value is not None) and (len(value) > 0)}


def searchMatrix(options, params, matrixname):
    searchfields = ['name', 'description']
    cache = {}
    results = {}
    if not matrixname:
        return {}
    cache = loadCache(options, matrixname)
    if not cache:
        return results
    for query in params:
        for entitytype in cache[matrixname].keys():
            if not results.get(entitytype):
                results[entitytype] = {}
            for entity in cache[matrixname][entitytype].keys():
                for fieldname in searchfields:
                    if isinstance(cache[matrixname][entitytype][entity][fieldname], list):
                        for item in cache[matrixname][entitytype][entity][fieldname]:
                            if query.lower() in item.lower():
                                if not results[entitytype].get(entity):
                                    results[entitytype][entity] = unfoldKeys(options, cache, matrixname, entitytype, entity)
                    else:
                        if query.lower() in cache[matrixname][entitytype][entity][fieldname]:
                            if not results[entitytype].get(entity):
                                results[entitytype][entity] = unfoldKeys(options, cache, matrixname, entitytype, entity)
    return {key: value for key, value in results.items() if (value is not None) and (len(value) > 0)}


def unfoldKeys(options, cache, matrixname, entitytype, entity):
    unfoldFields = ['Actors', 'Malwares', 'Mitigations', 'Subtechniques', 'Techniques']
    results = {
        'name': cache[matrixname][entitytype][entity]['name'],
        'description': cache[matrixname][entitytype][entity]['description'],
    }
    for unfoldField in unfoldFields:
        if unfoldField in cache[matrixname][entitytype][entity].keys():
            if len(cache[matrixname][entitytype][entity][unfoldField])>0:
                results[unfoldField] = {}
                for key in cache[matrixname][entitytype][entity][unfoldField]:
                    if cache[matrixname][unfoldField].get(key):
                        results[unfoldField][key] = {
                            'name': cache[matrixname][unfoldField][key]['name'],
                            'description': cache[matrixname][unfoldField][key]['description'],
                        }
                    else:
                        results[unfoldField][key] = {
                            'name': key,
                            'description': '*** DEPRECATED OR REVOKED ' +
                                           unfoldField.rstrip('s').upper() + ' ***',
                        }
                    pass
    return results


def Transform(options, AttackMatrix):
    matrix = {
        options.matrix: {},
    }
    # Create all tactics
    matrix[options.matrix]['Tactics'] = {}
    for entry in AttackMatrix['objects']:
        if not entry.get('revoked') or (entry.get('revoked') and options.revoked):
            if not entry.get('x_mitre_deprecated') or (entry.get('x_mitre_deprecated') and options.deprecated):
                if entry.get('type'):
                    if entry['type'] == 'x-mitre-tactic':
                        # Tactic
                        tactic = entry['name']
                        description = entry['description']
                        for external_reference in entry['external_references']:
                            if external_reference.get('external_id'):
                                if 'mitre' and 'attack' in external_reference['source_name'].lower():
                                    id = external_reference['external_id']
                        matrix[options.matrix]['Tactics'][id] = {
                                'name': tactic,
                                'description': description,
                                'Techniques': [],
                        }
    # Create all techniques
    matrix[options.matrix]['Techniques'] = {}
    for entry in AttackMatrix['objects']:
        if not entry.get('revoked') or (entry.get('revoked') and options.revoked):
            if not entry.get('x_mitre_deprecated') or (entry.get('x_mitre_deprecated') and options.deprecated):
                if entry.get('type'):
                    if entry['type'] == 'attack-pattern':
                        if entry.get('x_mitre_is_subtechnique'):
                            if not entry['x_mitre_is_subtechnique']:
                                subtechnique = False
                            else:
                                subtechnique = True
                        else:
                            subtechnique = False
                        # Not a subtechnique
                        if not subtechnique:
                            technique = entry['name']
                            if entry.get('description'):
                                description = entry['description']
                            else:
                                description = 'Not available.'
                            for external_reference in entry['external_references']:
                                if external_reference.get('external_id'):
                                    if 'mitre' and 'attack' in external_reference['source_name'].lower():
                                        id = external_reference['external_id']
                            matrix[options.matrix]['Techniques'][id] = {
                                    'name': technique,
                                    'description': description,
                                    'Actors': [],
                                    'Malwares': [],
                                    'Mitigations': [],
                                    'Subtechniques': [],
                                    'Tools': [],
                            }
                            if entry.get('kill_chain_phases'):
                                for kill_chain_type in entry['kill_chain_phases']:
                                    if ('mitre' and 'attack' in kill_chain_type['kill_chain_name']) and kill_chain_type.get('phase_name'):
                                        phase_name = string.capwords(kill_chain_type['phase_name'].replace('-', ' '))
                                        for tactic in matrix[options.matrix]['Tactics']:
                                            if matrix[options.matrix]['Tactics'][tactic]['name'].lower() in phase_name.lower():
                                                if id not in matrix[options.matrix]['Tactics'][tactic]['Techniques']:
                                                    matrix[options.matrix]['Tactics'][tactic]['Techniques'].append(id)
    # Create all subtechniques
    matrix[options.matrix]['Subtechniques'] = {}
    for entry in AttackMatrix['objects']:
        if not entry.get('revoked') or (entry.get('revoked') and options.revoked):
            if not entry.get('x_mitre_deprecated') or (entry.get('x_mitre_deprecated') and options.deprecated):
                if entry.get('type'):
                    if entry['type'] == 'attack-pattern':
                        if entry.get('x_mitre_is_subtechnique'):
                            if entry['x_mitre_is_subtechnique']:
                                subtechnique = entry['name']
                                if entry.get('description'):
                                    description = entry['description']
                                else:
                                    description = 'Not available.'
                                for external_reference in entry['external_references']:
                                    if external_reference.get('external_id'):
                                        if 'mitre' and 'attack' in external_reference['source_name'].lower():
                                            id = external_reference['external_id']
                                            technique = id.split('.')[0]
                                            techniquename = matrix[options.matrix]['Techniques'][technique]['name']
                            matrix[options.matrix]['Subtechniques'][id] = {
                                    'name': subtechnique,
                                    'subtechnique_of': technique,
                                    'description': description,
                                    'Actors': [],
                                    'Malwares': [],
                                    'Mitigations': [],
                                    'Subtechniques': [],
                                    'Tools': [],
                            }
                            matrix[options.matrix]['Techniques'][technique]['Subtechniques'].append(id)
    # Create all actors
    matrix[options.matrix]['Actors'] = {}
    for entry in AttackMatrix['objects']:
        if not entry.get('revoked') or (entry.get('revoked') and options.revoked):
            if not entry.get('x_mitre_deprecated') or (entry.get('x_mitre_deprecated') and options.deprecated):
                if entry.get('type'):
                    if entry['type'] == 'intrusion-set':
                        if entry.get('aliases'):
                            names = entry['aliases']
                        else:
                            names = entry['name']
                        if entry.get('description'):
                            description = entry['description']
                        else:
                            description = 'Not available.'
                        for external_reference in entry['external_references']:
                            if external_reference.get('external_id'):
                                if 'mitre' and 'attack' in external_reference['source_name'].lower():
                                    id = external_reference['external_id']
                        matrix[options.matrix]['Actors'][id] = {
                                'name': names,
                                'description': description,
                                'Malwares': [],
                                'Subtechniques': [],
                                'Techniques': [],
                                'Tools': [],
                        }
    # Create all malwares
    matrix[options.matrix]['Malwares'] = {}
    for entry in AttackMatrix['objects']:
        if not entry.get('revoked'):
            if not entry.get('x_mitre_deprecated') or (entry.get('x_mitre_deprecated') and options.deprecated):
                if entry.get('type'):
                    if entry['type'] == 'malware':
                        names = entry['x_mitre_aliases']
                        if entry.get('description'):
                            description = entry['description']
                        else:
                            description = 'Not available.'
                        for external_reference in entry['external_references']:
                            if external_reference.get('external_id'):
                                if 'mitre' and 'attack' in external_reference['source_name'].lower():
                                    id = external_reference['external_id']
                        matrix[options.matrix]['Malwares'][id] = {
                                'name': names,
                                'description': description,
                                'Actors': [],
                                'Subtechniques': [],
                                'Techniques': [],
                        }
    # Create all mitigations
    matrix[options.matrix]['Mitigations'] = {}
    for entry in AttackMatrix['objects']:
        if not entry.get('revoked') or (entry.get('revoked') and options.revoked):
            if not entry.get('x_mitre_deprecated') or (entry.get('x_mitre_deprecated') and options.deprecated):
                if entry.get('type'):
                    if entry['type'] == 'course-of-action':
                        names = entry['name']
                        description = entry['description']
                        for external_reference in entry['external_references']:
                            if external_reference.get('external_id'):
                                if 'mitre' and 'attack' in external_reference['source_name'].lower():
                                    id = external_reference['external_id']
                        matrix[options.matrix]['Mitigations'][id] = {
                                'name': names,
                                'description': description,
                                'Subtechniques': [],
                                'Techniques': [],
                        }
    # Create all tools
    matrix[options.matrix]['Tools'] = {}
    for entry in AttackMatrix['objects']:
        if not entry.get('revoked'):
            if not entry.get('x_mitre_deprecated') or (entry.get('x_mitre_deprecated') and options.deprecated):
                if entry.get('type'):
                    if entry['type'] == 'tool':
                        names = entry['x_mitre_aliases']
                        description = entry['description']
                        for external_reference in entry['external_references']:
                            if external_reference.get('external_id'):
                                if 'mitre' and 'attack' in external_reference['source_name'].lower():
                                    id = external_reference['external_id']
                        matrix[options.matrix]['Tools'][id] = {
                                'name': names,
                                'description': description,
                                'Actors': [],
                                'Subtechniques': [],
                                'Techniques': [],
                        }
    # LINK ALL THE THINGS!
    for entry in AttackMatrix['objects']:
        if not entry.get('revoked') or (entry.get('revoked') and options.revoked):
            if not entry.get('x_mitre_deprecated') or (entry.get('x_mitre_deprecated') and options.deprecated):
                if entry.get('type'):
                    if entry.get('relationship_type'):
                        relationship_type = entry['relationship_type']
                    if entry['type'] == 'relationship' and (relationship_type == 'mitigates' or relationship_type == 'uses'):
                        source = entry['source_ref']
                        target = entry['target_ref']
                        sourceid = None
                        targetid = None
                        for sourceentry in AttackMatrix['objects']:
                            if sourceentry['id'].lower() == source.lower():
                                if sourceentry['type'] == 'attack-pattern':
                                    sourcetype = 'Techniques'
                                if sourceentry['type'] == 'intrusion-set':
                                    sourcetype = 'Actors'
                                if sourceentry['type'] == 'malware':
                                    sourcetype = 'Malwares'
                                if sourceentry['type'] == 'course-of-action':
                                    sourcetype = 'Mitigations'
                                if sourceentry['type'] == 'tool':
                                    sourcetype = 'Tools'
                                for external_reference in sourceentry['external_references']:
                                    if external_reference.get('external_id'):
                                        if 'mitre' and 'attack' in external_reference['source_name'].lower():
                                            sourceid = external_reference['external_id']
                                            if '.' in sourceid:
                                                sourcetype = 'Subtechniques'
                        for targetentry in AttackMatrix['objects']:
                            if targetentry['id'].lower() == target.lower():
                                if targetentry['type'] == 'attack-pattern':
                                    targettype = 'Techniques'
                                if targetentry['type'] == 'intrusion-set':
                                    targettype = 'Actors'
                                if targetentry['type'] == 'malware':
                                    targettype = 'Malwares'
                                if targetentry['type'] == 'course-of-action':
                                    targettype = 'Mitigations'
                                if targetentry['type'] == 'tool':
                                    targettype = 'Tools'
                                for external_reference in targetentry['external_references']:
                                    if external_reference.get('external_id'):
                                        if 'mitre' and 'attack' in external_reference['source_name'].lower():
                                            targetid = external_reference['external_id']
                                            if '.' in targetid:
                                                targettype = 'Subtechniques'
                        if (sourceid and targetid) and (sourceid != targetid):
                            try:
                                if targetid not in matrix[options.matrix][sourcetype][sourceid][targettype]:
                                    matrix[options.matrix][sourcetype][sourceid][targettype].append(targetid)
                            except KeyError:
                                if options.verbose:
                                    print('\'' + sourcetype + '->' + sourceid + '\' cannot be linked to \'' +
                                          targettype + '->' + targetid + '\' - deprecated/revoked entries?')
                                pass
                            try:
                                if sourceid not in matrix[options.matrix][targettype][targetid][sourcetype]:
                                    matrix[options.matrix][targettype][targetid][sourcetype].append(sourceid)
                            except KeyError:
                                if options.verbose:
                                    print('\'' + targettype + '->' + targetid + '\' cannot be linked to \'' +
                                          sourcetype + '->' + sourceid + '\' - deprecated/revoked entries?')
                                pass
    return matrix


def GenerateMatrix(options):
    if Matrices.get(options.matrix):
        file, url = options.cachedir+'/'+Matrices[options.matrix]['file'], Matrices[options.matrix]['url']
        jsonfile = pathlib.Path(file)
        if not jsonfile.exists() or options.force:
            try:
                logging.info('Downloading ' + url)
                with urllib.request.urlopen(url) as response, open(jsonfile, 'wb') as outfile:
                    shutil.copyfileobj(response, outfile)
            except urllib.error.HTTPError as e:
                logging.error('Download of ' + url + ' failed: ' + e.reason)
        with open(jsonfile, 'rb') as matrix:
            # We have the file now, let's get to work
            try:
                logging.info('Parsing ' + file)
                return(Transform(options, json.load(matrix)))
            except json.JSONDecodeError:
                logging.error(url + ' contains malformed JSON')
    else:
        logging.error('ATT&CK ' + options.matrix + ' has no definition in the configuration.')


if __name__ == "__main__":
    '''
    Interactive run from the command-line
    '''
    parser = argparse.ArgumentParser(description='MITRE ATT&CK® Matrix parser'
                                                 ' - can be run directly to '
                                                 'provide an API or imported '
                                                 'as a module to provide a '
                                                 'Python dictionary.')
    parser.add_argument('-t', '--matrix',
                        dest='matrix',
                        required=False,
                        default=options.matrix,
                        help='[optional] The ATT&CK Matrix to parse '
                             '(default: ' + options.matrix + '). This is '
                             'downloaded and locally cached afterwards.')
    parser.add_argument('-f', '--force',
                        dest='force',
                        action='store_true',
                        default=options.force,
                        help='[optional] Redownload the matrix and overwrite '
                             'the cache file (clean run).')
    parser.add_argument('--deprecated',
                        required=False,
                        action='store_true',
                        default=options.deprecated,
                        help='[optional] Should the parser include deprecated '
                             'objects from the JSON into the matrix '
                             '(default: ' + str(options.deprecated) + ').')
    parser.add_argument('--revoked',
                        required=False,
                        action='store_true',
                        default=options.revoked,
                        help='[optional] Should the parser include revoked '
                             'objects from the JSON into the matrix '
                             '(default: ' + str(options.revoked) + ').')
    parser.add_argument('-d', '--daemonize',
                        dest='daemonize',
                        action='store_true',
                        default=False,
                        help='[optional] Daemonize and provide an API that '
                              'can be queried via webclients to return matrix '
                              'data (see docs).')
    parser.add_argument('-i', '--ip',
                        dest='ip',
                        default=options.ip,
                        required=False,
                        help='[optional] Host the daemon should listen '
                             'on (default: ' + options.ip + ').')
    parser.add_argument('-p', '--port',
                        dest='port',
                        default=options.port,
                        required=False,
                        help='[optional] Port the daemon should listen '
                             'on (default: ' + str(options.port) + ').')
    parser.add_argument('-k', '--key',
                        dest='token',
                        default=options.token,
                        required=False,
                        help='[optional] Block all web access unless a '
                             'valid token is offered (default: ' +
                             str(options.token) + ').')
    parser.add_argument('-v', '--verbose',
                        dest='verbose',
                        action='store_true',
                        default=options.verbose,
                        help='[optional] Print lots of debugging and verbose '
                             'information about what\'s happening (default: '
                             'disabled).')
    parser.add_argument('-l', '--logfile',
                        dest='logfile',
                        default=options.logfile,
                        help='[optional] Logfile for log output (default: \'' +
                             options.logfile + '\')')
    parser.add_argument('-c', '--cachedirr',
                        dest='cachedir',
                        default=options.cachedir,
                        help='[optional] Directory to write caches to (default: \'' +
                             options.cachedir + '\')')
    parser.add_argument('-a', '--cacheaffix',
                        dest='cacheaffix',
                        default=options.cacheaffix,
                        help='[optional] Affix for cache file names (default: \'' +
                             options.cacheaffix + '\')')
    options = parser.parse_args()
    logging.basicConfig(filename=options.logfile, level=logging.INFO)
    if not options.daemonize:
        cachefile = pathlib.Path(options.cachedir.rstrip('/')+'/'+options.matrix+options.cacheaffix)
        if not cachefile.exists() or options.force:
            if options.verbose:
                logging.info('Generating the cachefile ' + cachefile.name)
            matrix = GenerateMatrix(options)
            with open(cachefile, 'wb') as cache:
                pickle.dump(matrix, cache, protocol=pickle.HIGHEST_PROTOCOL)
        else:
            if options.verbose:
                logging.info('Loading the cachefile ' + cachefile.name)
                matrices = loadCaches(options)
                pprint.pprint(matrices[options.matrix])
            else:
                parser.print_help()
    else:
        try:
            port = int(options.port)
        except ValueError:
            logging.error('The listening port must be a numeric value')
        uvicorn.run('attackmatrix:app', host=options.ip, port=options.port, log_level='info', reload=True)
else:
    '''
    Module import: generateMatrix() to get a Python dict
    '''
