"""Offline native-environment readiness analysis; never executes project/package code."""
import hashlib
import json
import re
import xml.etree.ElementTree as ET

from preflight.petclinic_adapter import AdmissionError,digest
from preflight.petclinic_source_intake import collect_archive


def pinned_requirements(raw):
    pins=[];seen=set()
    for line in raw.decode('utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        match=re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9_.-]*)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)',line)
        if not match:raise AdmissionError('Only literal exact requirement pins supported; no hooks/options/ranges')
        name=re.sub(r'[-_.]+','-',match[1]).lower()
        if name in seen:raise AdmissionError('Duplicate or conflicting requirement pin')
        seen.add(name);pins.append((line,match[1],match[2]))
    if not pins:raise AdmissionError('No pinned dependencies found')
    return pins


def python_readiness(requirements,metadata):
    pins=pinned_requirements(requirements)
    if metadata['requirements_sha256']!=hashlib.sha256(requirements).hexdigest():
        raise AdmissionError('Release metadata not bound to exact project requirements')
    releases={r['requirement']:r for r in metadata['releases']}
    if len(releases)!=len(metadata['releases']) or set(releases)!={p[0] for p in pins}:
        raise AdmissionError('Missing/extra release evidence')
    results=[]
    for pin,name,version in pins:
        release=releases[pin]
        if release['metadata_url']!='https://pypi.org/pypi/'+name+'/'+version+'/json':
            raise AdmissionError('Release metadata origin/version mismatch')
        artifacts=release['artifacts'];wheels=[]
        if type(artifacts) is not list:raise AdmissionError('Artifact evidence list required')
        for artifact in artifacts:
            if artifact['packagetype']=='bdist_wheel':
                if not artifact['filename'].endswith('.whl'):raise AdmissionError('Inconsistent wheel evidence')
                wheels.append(artifact['filename'])
        results.append({'requirement':pin,'wheel_files':wheels,
                        'status':'wheels_present_compatibility_unverified' if wheels else 'no_wheel_in_recorded_release',
                        'metadata_url':release['metadata_url']})
    missing=[r['requirement'] for r in results if not r['wheel_files']]
    return {'status':'blocked_wheel_only_acquisition' if missing else 'compatibility_and_closure_review_required',
            'requirements_sha256':hashlib.sha256(requirements).hexdigest(),'release_evidence_sha256':digest(metadata),
            'snapshot_date':metadata['retrieved_on'],'requirements_without_wheels':missing,'releases':results,
            'ready_for_native_tests':False,'baseline_executed':False,
            'limitations':['Presence of a wheel does not establish platform/runtime compatibility or transitive closure.',
                           'An absent wheel in this snapshot is not a universal claim about all environments.',
                           'Reviewed preinstalled environments/source builds would be separate capabilities, not automatic fallbacks.']}


def maven_readiness(raw):
    text=raw.decode('utf-8')
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():raise AdmissionError('XML declarations forbidden')
    root=ET.fromstring(text)
    ns=root.tag[:-len('project')] if root.tag.endswith('project') else ''
    if root.tag.split('}')[-1]!='project':raise AdmissionError('Not a Maven project')
    def coordinate(node):
        return {key:node.findtext(ns+key) for key in ('groupId','artifactId','version')}
    parent=root.find(ns+'parent')
    dependencies=[{**coordinate(n),'scope':n.findtext(ns+'scope') or 'compile'}
                  for n in root.findall(ns+'dependencies/'+ns+'dependency')]
    plugins=[coordinate(n) for n in root.findall(ns+'build/'+ns+'plugins/'+ns+'plugin')]
    return {'status':'blocked_complete_maven_environment_missing','pom_sha256':hashlib.sha256(raw).hexdigest(),
            'declared_parent':coordinate(parent) if parent is not None else None,
            'declared_java_version':root.findtext(ns+'properties/'+ns+'java.version'),
            'direct_dependencies':dependencies,'direct_plugins':plugins,
            'native_test_dependencies_declared':any(d['scope']=='test' for d in dependencies),
            'dependency_management_resolved':False,'transitive_closure_verified':False,
            'ready_for_native_tests':False,'baseline_executed':False,
            'blockers':['complete_reviewed_parent_BOM_plugin_test_dependency_closure_not_supplied',
                        'offline_dependency_bundle_execution_not_connected_to_HTTP_service_lifecycle'],
            'limitations':['This is literal POM analysis, not Maven model/plugin resolution.',
                           'No native build failure or application defect has been observed.']}


def qualify(descriptor,baseline,candidate,profile,metadata=None):
    from preflight.petclinic_adapter import exact
    from preflight.execution_manifest import path,commands
    exact(profile,{'schema','language','root','dependency_manifest','native_tests'})
    if profile['schema']!='wheel-native-readiness-profile-v1' or profile['language']!=descriptor['language']:
        raise AdmissionError('Readiness profile differs from source language')
    path(profile['root'],allow_root=True);path(profile['dependency_manifest'])
    commands(profile['native_tests'],required=True)
    dependency_path=('' if profile['root']=='.' else profile['root']+'/')+profile['dependency_manifest']
    files={side:collect_archive(raw,descriptor['archives'][side]['sha256'],descriptor['archives'][side]['root'])
           for side,raw in [('baseline',baseline),('candidate',candidate)]}
    if any(dependency_path not in value for value in files.values()):raise AdmissionError('Dependency manifest missing from admitted sources')
    if descriptor['language']=='python':
        if metadata is None:raise AdmissionError('Pinned release metadata evidence required')
        reports={side:python_readiness(files[side][dependency_path],metadata) for side in files}
    elif descriptor['language']=='java':
        reports={side:maven_readiness(files[side][dependency_path]) for side in files}
    else:raise AdmissionError('Unsupported readiness language')
    return {'schema':'wheel-native-readiness-v1','candidate_id':descriptor['id'],'descriptor_sha256':digest(descriptor),
            'status':'environment_blocked_before_native_execution','revisions':reports,
            'project_or_package_code_executed':False,'model_requests':0,'comparison_registry_changed':False,
            'desired_native_pass_achieved':False,'profile_sha256':digest(profile),'native_tests_requested':profile['native_tests']}
