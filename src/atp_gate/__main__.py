"""ATP Gate: fail-closed paper decisions and separate historical research commands."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError
from .historical_audit import audit_tennis_data_csv


def evaluate(data):
    """Lazy compatibility hook for the gate CLI and existing callers/tests."""
    from .policy import evaluate as gate_evaluate
    return gate_evaluate(data)


def main() -> int:
    parser=argparse.ArgumentParser(prog='python -m atp_gate',description='ATP paper-only gate and historical research')
    sub=parser.add_subparsers(dest='cmd',required=True)
    sub.add_parser('evaluate',help='Validate one pre-match JSON; default model registry is empty').add_argument('path')
    sub.add_parser('audit',help='Legacy historical tennis-data CSV quality check').add_argument('path')
    research_audit=sub.add_parser('research-audit',help='Audit one or more historical ATP result/odds CSVs')
    research_audit.add_argument('paths',nargs='+')
    research_verify=sub.add_parser('research-verify',help='Check input hashes of a historical report; NO model certification')
    research_verify.add_argument('report',help='Path to research JSON report')
    research_verify.add_argument('sources',nargs='+',help='Original historical source CSV/XLSX files')
    research_profile=sub.add_parser('research-profile',help='Read-only accepted-match coverage / missingness by ATP season')
    research_profile.add_argument('--start-year',type=int)
    research_profile.add_argument('--end-year',type=int)
    research_profile.add_argument('paths',nargs='+',help='Original historical CSV/XLSX source files')
    valuebetennis_profile=sub.add_parser('valuebetennis-profile',help='Read-only ATP identity and coverage preflight for Valuebetennis CSVs')
    valuebetennis_profile.add_argument('--start-year',type=int)
    valuebetennis_profile.add_argument('--end-year',type=int)
    valuebetennis_profile.add_argument('paths',nargs='+',help='Local semicolon-delimited Valuebetennis seasonal CSVs')
    tourney_inventory=sub.add_parser('valuebetennis-tournaments',help='Inventory provider tournament-season IDs and raw draw rounds; no tier inference')
    tourney_inventory.add_argument('--start-year',type=int)
    tourney_inventory.add_argument('--end-year',type=int)
    tourney_inventory.add_argument('--out',required=True,help='Local ignored JSON report filename')
    tourney_inventory.add_argument('paths',nargs='+',help='Valuebetennis seasonal CSV inputs')
    inventory_review=sub.add_parser('valuebetennis-review',help='Read-only integrity and anomaly review of saved tournament JSON')
    inventory_review.add_argument('report',help='P1.3a saved source inventory JSON')
    inventory_review.add_argument('--out',help='Optional separate JSON report under ignored reports directory')
    tier_audit=sub.add_parser('valuebetennis-tier-audit',help='Audit explicit official-tier claims against pinned tournament JSON; never authorise training')
    tier_audit.add_argument('inventory',help='P1.3a saved tournament inventory JSON')
    tier_audit.add_argument('registry',help='Source-backed per-event tier registry JSON')
    tier_audit.add_argument('--out',help='Optional separate local JSON audit report')
    calendar_audit=sub.add_parser('valuebetennis-calendar-audit',help='Compare curated official ATP events against pinned provider inventory, no training authorization')
    calendar_audit.add_argument('inventory',help='Original saved P1.3a Valuebetennis tournament JSON')
    calendar_audit.add_argument('calendar',help='Curated official ATP calendar reference JSON')
    calendar_audit.add_argument('--out',help='Optional separate local JSON report')
    gap_forensics=sub.add_parser('valuebetennis-gap-forensics',help='Investigate original local CSV source rows behind official ATP gaps; no source mutation')
    gap_forensics.add_argument('csv_path',help='One original local Valuebetennis season CSV')
    gap_forensics.add_argument('inventory',help='Pinned P1.3a tournament source inventory JSON')
    gap_forensics.add_argument('calendar',help='Curated official ATP event calendar JSON')
    gap_forensics.add_argument('--month',required=True,help='UTC month YYYY-MM')
    gap_forensics.add_argument('--out',help='Optional separate JSON report under ignored reports directory')
    legacy_crosswalk=sub.add_parser('valuebetennis-legacy-crosswalk',help='Review metadata-only legacy provider event IDs against pinned official ATP calendar')
    legacy_crosswalk.add_argument('inventory',help='Original pinned P1.3a tournament inventory JSON')
    legacy_crosswalk.add_argument('calendar',help='Curated official ATP February 2024 event reference')
    legacy_crosswalk.add_argument('manifest',help='Curated legacy provider HTML tournament-index metadata')
    legacy_crosswalk.add_argument('--out',help='Optional local JSON report under ignored reports directory')
    tml_feb=sub.add_parser('tml-february-audit',help='Audit local TML ATP February 2024 candidates; personal noncommercial research only')
    tml_feb.add_argument('csv_path',help='Locally downloaded TML 2024.csv')
    tml_feb.add_argument('crosswalk',help='Curated TML-to-official 2024 February event registry')
    tml_feb.add_argument('official',help='Pinned official ATP 2024 February calendar registry')
    tml_feb.add_argument('--out',help='Optional ignored local JSON audit report')
    tml_update=sub.add_parser('tml-update',help='Owner-invoked daily versioned TML CSV refresh; private noncommercial only')
    tml_update.add_argument('--year',required=True,type=int,help='ATP season year')
    tml_update.add_argument('--root',default='data/tml',help='Private locally ignored versioned snapshot directory')
    tml_update.add_argument('--force',action='store_true',help='Explicitly bypass daily freshness check')

    elo_research=sub.add_parser('tml-elo-experiment',help='Local noncommercial pre-tournament Elo skill study; not betting forecasts')
    elo_research.add_argument('paths',nargs='+',help='Local TML YYYY.csv or immutable YYYY-SHA256.csv snapshots')
    elo_research.add_argument('--out',required=True,help='Aggregate-only local JSON report path')
    elo_research.add_argument('--embargo-days',type=int,default=28,help='Fixed tournament-result availability embargo (default 28 days)')
    elo_research.add_argument('--bootstrap-replicates',type=int,default=200,help='Event-cluster bootstrap repeats (default 200)')
    elo_research.add_argument('--normalize-level-a-2024',action='store_true',help='Opt-in exact reviewed 2024 source normalization')
    tml_cross=sub.add_parser('tml-crosspublication-audit',help='Crosscheck TML and Sackmann 2024 ATP candidate matches; personal noncommercial only')
    tml_cross.add_argument('tml_csv',help='Local TML 2024.csv')
    tml_cross.add_argument('archive_csv',help='Local Sackmann-format atp_matches_2024.csv')
    tml_cross.add_argument('crosswalk',help='Curated 2024 February event registry')
    tml_cross.add_argument('aliases',help='Pinned explicit player display-name alias registry')
    tml_cross.add_argument('--out',help='Optional aggregate-only JSON report, not an input file')
    source_intake=sub.add_parser('historical-source-intake',help='Verify pinned local correction-source bytes and permission review; never unlock training')
    source_intake.add_argument('artifact',help='Local, separately acquired match-level CSV')
    source_intake.add_argument('manifest',help='Correction-source provenance/rights manifest JSON')
    source_intake.add_argument('inventory',help='Pinned historical inventory JSON')
    source_intake.add_argument('official',help='Curated official ATP event reference JSON')
    source_intake.add_argument('--out',help='Optional local review report (never an input path)')
    research_train=sub.add_parser('research-train',help='XGBoost research with chronological split; NO live allocation')
    research_train.add_argument('paths',nargs='+')
    research_train.add_argument('--out',required=True,help='JSON research report output path')
    research_train.add_argument('--minimum-total',type=int,default=200)
    research_train.add_argument('--minimum-target',type=int,default=30)
    research_train.add_argument('--seed',type=int,default=20261123)
    args=parser.parse_args()

    if args.cmd=='tml-elo-experiment':
        try:
            from .tml_elo_experiment import run_tml_elo_experiment
            sources=[Path(p) for p in args.paths]
            dest=Path(args.out)
            if dest.resolve() in {p.resolve() for p in sources}:
                raise ValueError('research report cannot overwrite any TML source snapshot')
            result=run_tml_elo_experiment(
                sources,
                embargo_days=args.embargo_days,
                bootstrap_replicates=args.bootstrap_replicates,
                normalize_level_a_2024=args.normalize_level_a_2024,
            )
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,UnicodeError,TypeError,KeyError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'PERSONAL_NONCOMMERCIAL_RESEARCH',
                'reason':str(exc),'model_validation_trusted':False,
                't60_quote_verified':False,'market_edge_verified':False,
                'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='tml-update':
        try:
            from datetime import datetime,timezone
            from .tml_snapshot import update_tml_season
            result=update_tml_season(
                args.year,Path(args.root),at=datetime.now(timezone.utc),
                force=args.force,
            )
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,TypeError,UnicodeError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'PERSONAL_NONCOMMERCIAL_RESEARCH',
                'reason':str(exc),'eligible_for_model_training':0,
                'allocation_enabled':False,'t60_quote_verified':False,
                'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='tml-crosspublication-audit':
        try:
            from .tml_sackmann_crosscheck import audit_tml_sackmann_crosspublication

            files=[Path(args.tml_csv),Path(args.archive_csv),
                   Path(args.crosswalk),Path(args.aliases)]
            if args.out and Path(args.out).resolve() in {p.resolve() for p in files}:
                raise ValueError('crosspublication report cannot overwrite an input')
            reg=json.loads(files[2].read_text(encoding='utf-8-sig'))
            names=json.loads(files[3].read_text(encoding='utf-8-sig'))
            report=audit_tml_sackmann_crosspublication(files[0],files[1],reg,names)
            if args.out:
                dest=Path(args.out)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',
                                encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,UnicodeError,TypeError,KeyError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'PERSONAL_NONCOMMERCIAL_RESEARCH',
                'reason':str(exc),'official_match_draw_verified':False,
                'source_independence_verified':False,
                'eligible_for_model_training':0,'allocation_enabled':False,
                'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='tml-february-audit':
        try:
            from .tml_historical_audit import audit_tml_february_2024

            source=Path(args.csv_path)
            crosswalk_file=Path(args.crosswalk)
            official_file=Path(args.official)
            inputs={p.resolve() for p in (source,crosswalk_file,official_file)}
            if args.out and Path(args.out).resolve() in inputs:
                raise ValueError('TML audit report cannot overwrite any source/registry input')
            crosswalk=json.loads(crosswalk_file.read_text(encoding='utf-8-sig'))
            official=json.loads(official_file.read_text(encoding='utf-8-sig'))
            report=audit_tml_february_2024(source,crosswalk,official)
            if args.out:
                dest=Path(args.out)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',
                                encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,UnicodeError,TypeError,KeyError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'PERSONAL_NONCOMMERCIAL_RESEARCH',
                'reason':str(exc),'main_draw_verified':False,
                'individual_match_start_verified':False,
                'eligible_for_model_training':0,'allocation_enabled':False,
                't60_quote_verified':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='historical-source-intake':
        try:
            from datetime import datetime, timezone
            import hashlib
            from .source_intake import audit_source_intake

            artifact=Path(args.artifact)
            manifest_path=Path(args.manifest)
            inventory_path=Path(args.inventory)
            official_path=Path(args.official)
            original_inputs={p.resolve() for p in (
                artifact,manifest_path,inventory_path,official_path
            )}
            if args.out and Path(args.out).resolve() in original_inputs:
                raise ValueError('intake report cannot overwrite an input')
            inventory_bytes=inventory_path.read_bytes()
            digest=hashlib.sha256(inventory_bytes).hexdigest()
            official=json.loads(official_path.read_text(encoding='utf-8-sig'))
            if (not isinstance(official,dict)
                    or official.get('inventory_sha256')!=digest
                    or not isinstance(official.get('events'),list)):
                raise ValueError('official event calendar not bound to inventory SHA256')
            keys=set()
            for item in official['events']:
                if not isinstance(item,dict) or not isinstance(item.get('event_key'),str):
                    raise ValueError('invalid official event reference')
                if item['event_key'] in keys:
                    raise ValueError('duplicate official event reference')
                keys.add(item['event_key'])
            manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
            result=audit_source_intake(
                artifact,manifest,inventory_sha256=digest,
                allowed_event_keys=keys,as_of=datetime.now(timezone.utc),
            )
            if args.out:
                dest=Path(args.out)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,UnicodeError,TypeError,KeyError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'HISTORICAL_RESEARCH_ONLY',
                'reason':str(exc),'rights_reviewed':False,
                'event_identity_verified':False,'main_draw_verified':False,
                't60_quote_verified':False,'eligible_for_model_training':0,
                'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='valuebetennis-legacy-crosswalk':
        try:
            import hashlib
            from .legacy_archive_crosswalk import audit_legacy_archive_crosswalk
            original_path=Path(args.inventory)
            calendar_path=Path(args.calendar)
            manifest_path=Path(args.manifest)
            inputs={original_path.resolve(),calendar_path.resolve(),manifest_path.resolve()}
            if args.out and Path(args.out).resolve() in inputs:
                raise ValueError('legacy crosswalk output cannot overwrite any input')
            original_bytes=original_path.read_bytes()
            original_digest=hashlib.sha256(original_bytes).hexdigest()
            inventory=json.loads(original_bytes.decode('utf-8-sig'))
            calendar=json.loads(calendar_path.read_text(encoding='utf-8-sig'))
            manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
            result=audit_legacy_archive_crosswalk(
                inventory,calendar,manifest,inventory_sha256=original_digest)
            if args.out:
                dest=Path(args.out)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({
                'status':result['status'],
                'mode':result['mode'],
                'inventory_sha256':original_digest,
                'official_event_count':result['official_event_count'],
                'crosswalk_entries':result['crosswalk_entries'],
                'archive_ids_absent_from_source':result['archive_ids_absent_from_source'],
                'legacy_archive_rights_verified':result['legacy_archive_rights_verified'],
                'legacy_match_results_available':result['legacy_match_results_available'],
                'warnings':result['warnings'],
                'report_path':str(args.out) if args.out else None,
                'tier_mapping_verified':False,'main_draw_verified':False,
                't60_quote_verified':False,
                'eligible_for_model_training':0,'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,UnicodeError,TypeError,KeyError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'HISTORICAL_RESEARCH_ONLY',
                'reason':str(exc),'legacy_archive_rights_verified':False,
                'legacy_match_results_available':False,
                'tier_mapping_verified':False,'main_draw_verified':False,
                't60_quote_verified':False,'eligible_for_model_training':0,
                'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='valuebetennis-gap-forensics':
        try:
            import hashlib
            from .source_gap_forensics import audit_source_gap
            raw_path=Path(args.csv_path)
            inventory_path=Path(args.inventory)
            calendar_path=Path(args.calendar)
            if args.out and Path(args.out).resolve() in (
                raw_path.resolve(),inventory_path.resolve(),calendar_path.resolve()
            ):
                raise ValueError('forensic output must not overwrite any input file')
            raw_inventory=inventory_path.read_bytes()
            inventory_hash=hashlib.sha256(raw_inventory).hexdigest()
            inventory=json.loads(raw_inventory.decode('utf-8-sig'))
            official=json.loads(calendar_path.read_text(encoding='utf-8-sig'))
            result=audit_source_gap(
                raw_path,inventory,official,
                inventory_sha256=inventory_hash,month=args.month)
            if args.out:
                dest=Path(args.out)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({
                'status':result['status'],
                'mode':result['mode'],
                'source_scope':result['source_scope'],
                'source_file':result['source_file'],
                'source_total_rows':result['source_total_rows'],
                'source_provisional_accepted':result['source_provisional_accepted'],
                'source_expected_accepted':result['source_expected_accepted'],
                'month':result['month'],
                'undated_rows_outside_month_attribution':result['undated_rows_outside_month_attribution'],
                'official_event_count':result['official_event_count'],
                'official_event_status_counts':result['official_event_status_counts'],
                'warnings':result['warnings'],
                'report_path':str(args.out) if args.out else None,
                'tier_mapping_verified':False,'main_draw_verified':False,
                't60_quote_verified':False,'eligible_for_model_training':0,
                'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,UnicodeError,TypeError,KeyError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'HISTORICAL_RESEARCH_ONLY',
                'reason':str(exc),'tier_mapping_verified':False,
                'main_draw_verified':False,'t60_quote_verified':False,
                'eligible_for_model_training':0,
                'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='valuebetennis-calendar-audit':
        try:
            import hashlib
            from .official_calendar_coverage import audit_official_calendar_coverage
            source_path=Path(args.inventory)
            official_path=Path(args.calendar)
            if args.out and Path(args.out).resolve() in (
                source_path.resolve(),official_path.resolve()
            ):
                raise ValueError('calendar report output cannot overwrite either input')
            source_bytes=source_path.read_bytes()
            official_bytes=official_path.read_bytes()
            source_sha=hashlib.sha256(source_bytes).hexdigest()
            source=json.loads(source_bytes.decode('utf-8-sig'))
            official=json.loads(official_bytes.decode('utf-8-sig'))
            result=audit_official_calendar_coverage(
                source,official,inventory_sha256=source_sha)
            result['official_calendar_file_sha256']=hashlib.sha256(official_bytes).hexdigest()
            if args.out:
                dest=Path(args.out)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({
                'status':result['status'],
                'mode':result['mode'],
                'inventory_sha256':source_sha,
                'source_tournament_groups':result['source_tournament_groups'],
                'official_event_count':result['official_event_count'],
                'official_events_by_tier':result['official_events_by_tier'],
                'missing_official_events':result['missing_official_events'],
                'missing_by_tier':result['missing_by_tier'],
                'candidate_official_events':result['candidate_official_events'],
                'ambiguous_official_events':result['ambiguous_official_events'],
                'warnings':result['warnings'],
                'report_path':str(args.out) if args.out else None,
                'tier_mapping_verified':False,'main_draw_verified':False,
                't60_quote_verified':False,'eligible_for_model_training':0,
                'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,UnicodeError,TypeError,KeyError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'HISTORICAL_RESEARCH_ONLY',
                'reason':str(exc),'tier_mapping_verified':False,
                'main_draw_verified':False,'t60_quote_verified':False,
                'eligible_for_model_training':0,
                'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='valuebetennis-tier-audit':
        try:
            import hashlib
            from .tier_registry import audit_tier_registry
            inventory_path=Path(args.inventory)
            registry_path=Path(args.registry)
            if args.out and Path(args.out).resolve() in (
                inventory_path.resolve(),registry_path.resolve()
            ):
                raise ValueError('tier audit output must not overwrite inventory or registry')
            original=inventory_path.read_bytes()
            source_sha=hashlib.sha256(original).hexdigest()
            inventory=json.loads(original.decode('utf-8-sig'))
            registry=json.loads(registry_path.read_text(encoding='utf-8-sig'))
            result=audit_tier_registry(
                inventory,registry,inventory_sha256=source_sha)
            if args.out:
                out_path=Path(args.out)
                out_path.parent.mkdir(parents=True,exist_ok=True)
                out_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({
                'status':result['status'],
                'mode':result['mode'],
                'inventory_sha256':source_sha,
                'tournament_season_groups':result['tournament_season_groups'],
                'candidate_matches':result['candidate_matches'],
                'reviewed_event_groups':result['reviewed_event_groups'],
                'unreviewed_event_groups':result['unreviewed_event_groups'],
                'reviewed_candidate_matches':result['reviewed_candidate_matches'],
                'history_only_matches':result['history_only_matches'],
                'potential_target_tier_matches':result['potential_target_tier_matches'],
                'known_incomplete_target_matches':result['known_incomplete_target_matches'],
                'expected_absent_event_count':result['expected_absent_event_count'],
                'warnings':result['warnings'],
                'report_path':str(args.out) if args.out else None,
                'tier_mapping_verified':False,'main_draw_verified':False,
                't60_quote_verified':False,
                'eligible_for_model_training':0,'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,UnicodeError,TypeError,KeyError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'HISTORICAL_RESEARCH_ONLY',
                'reason':str(exc),'tier_mapping_verified':False,
                'main_draw_verified':False,'t60_quote_verified':False,
                'eligible_for_model_training':0,'allocation_enabled':False,'stake':0
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='valuebetennis-review':
        try:
            import hashlib
            from .inventory_review import review_tournament_inventory
            source=Path(args.report)
            if args.out and Path(args.out).resolve()==source.resolve():
                raise ValueError('review output cannot overwrite the source inventory')
            raw=source.read_bytes()
            result=review_tournament_inventory(json.loads(raw.decode('utf-8-sig')))
            digest=hashlib.sha256(raw).hexdigest()
            result['input_report_sha256']=digest
            if args.out:
                destination=Path(args.out)
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({
                'status':result['status'],
                'mode':result['mode'],
                'input_report_sha256':digest,
                'tournament_season_groups':result['integrity']['tournament_season_groups'],
                'candidate_matches':result['integrity']['candidate_matches'],
                'cross_year_event_ids':len(result['cross_year_tournament_ids']),
                'special_format_groups':result['special_format_candidates']['group_count'],
                'special_format_matches':result['special_format_candidates']['candidate_matches'],
                'missing_final_code_groups':len(result['missing_final_code_candidates']),
                'large_event_start_gaps':len(result['large_event_start_gaps']),
                'warnings':result['warnings'],
                'report_path':str(args.out) if args.out else None,
                'tier_mapping_verified':False,'main_draw_verified':False,
                'eligible_for_model_training':0,'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 0
        except (ValueError,OSError,UnicodeError,TypeError,KeyError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'HISTORICAL_RESEARCH_ONLY',
                'reason':str(exc),'tier_mapping_verified':False,
                'main_draw_verified':False,'eligible_for_model_training':0,
                'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='valuebetennis-tournaments':
        try:
            from .valuebetennis_source import inspect_valuebetennis_sources
            result=inspect_valuebetennis_sources(
                args.paths, expected_start_year=args.start_year,
                expected_end_year=args.end_year, include_tournaments=True)
            inventory=result['tournament_inventory']
            dest=Path(args.out)
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({
                'status':inventory['status'],
                'mode':'HISTORICAL_RESEARCH_ONLY',
                'tournament_season_count':inventory['summary']['tournament_seasons'],
                'candidate_matches':inventory['summary']['candidate_matches'],
                'inventoried_matches':inventory['summary']['inventoried_matches'],
                'missing_tournament_metadata':inventory['summary']['missing_tournament_metadata'],
                'metadata_conflicts':inventory['summary']['metadata_conflicts'],
                'missing_expected_years':result['coverage']['missing_expected_years'],
                'warnings':inventory['warnings'],
                'report_path':str(dest),
                'tier_mapping_verified':False,'main_draw_verified':False,
                'eligible_for_model_training':0,'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 0 if inventory['status']=='INVENTORIED_UNMAPPED' else 2
        except (ValueError,OSError,UnicodeError,RuntimeError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'HISTORICAL_RESEARCH_ONLY',
                'reason':str(exc),'tier_mapping_verified':False,
                'main_draw_verified':False,'eligible_for_model_training':0,
                'allocation_enabled':False,'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='valuebetennis-profile':
        try:
            from .valuebetennis_source import inspect_valuebetennis_sources
            result=inspect_valuebetennis_sources(
                args.paths,expected_start_year=args.start_year,
                expected_end_year=args.end_year)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0 if result['status']=='INSPECTED_UNMAPPED' else 2
        except (ValueError,OSError,UnicodeError,RuntimeError) as exc:
            print(json.dumps({
                'status':'ERROR','mode':'HISTORICAL_RESEARCH_ONLY',
                'reason':str(exc),'live_eligible':False,
                'allocation_enabled':False,'validation_report_trusted':False,
                'eligible_for_model_training':0,'stake':0,
            },ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='research-verify':
        from .report_integrity import verify_research_report
        result=verify_research_report(Path(args.report),[Path(x) for x in args.sources])
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result['status']=='MATCH' else 2

    if args.cmd in ('research-audit','research-train','research-profile'):
        try:
            from .research_data import load_historical_matches
            if args.cmd=='research-audit':
                _matches,result=load_historical_matches(args.paths)
            elif args.cmd=='research-profile':
                from .source_profile import profile_historical_sources
                result=profile_historical_sources(
                    args.paths,expected_start_year=args.start_year,
                    expected_end_year=args.end_year)
            else:
                from .research_train import run_research
                result=run_research(args.paths,minimum_total=args.minimum_total,
                                    minimum_target=args.minimum_target,seed=args.seed)
                dest=Path(args.out)
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 2 if result.get('status')=='INCOMPLETE' else 0
        except (ValueError,OSError,RuntimeError) as exc:
            print(json.dumps({'status':'ERROR','mode':'HISTORICAL_RESEARCH_ONLY',
                              'reason':str(exc),'live_eligible':False,
                              'allocation_enabled':False},ensure_ascii=False,indent=2))
            return 2

    if args.cmd=='audit':
        try:
            print(json.dumps(audit_tennis_data_csv(args.path),ensure_ascii=False,indent=2))
            return 0
        except (ValueError,KeyError,FileNotFoundError):
            print(json.dumps({'decision':'ABSTAIN','stake':'0',
                              'reasons':['INVALID_CONTRACT'],'error_count':1},
                             ensure_ascii=False,indent=2))
            return 2

    try:
        from pydantic import ValidationError
        from .contracts import DecisionInput
        from . import policy  # check gate dependencies only on evaluate path
    except ImportError:
        print(json.dumps({'decision':'ABSTAIN','stake':'0',
                          'reasons':['GATE_DEPENDENCY_UNAVAILABLE']},indent=2))
        return 2
    try:
        data=DecisionInput.model_validate_json(Path(args.path).read_text(encoding='utf-8'))
        decision=evaluate(data)
        print(decision.model_dump_json(indent=2))
        return 0
    except ZoneInfoNotFoundError:
        print(json.dumps({'decision':'ABSTAIN','stake':'0',
                          'reasons':['TIMEZONE_DATABASE_MISSING'],
                          'help':'Install tzdata in this Python environment: python -m pip install tzdata'},
                         ensure_ascii=False, indent=2))
        return 3
    except (ValidationError,ValueError,KeyError,FileNotFoundError) as exc:
        print(json.dumps({'decision':'ABSTAIN','stake':'0',
                          'reasons':['INVALID_CONTRACT'],
                          'error_count':len(exc.errors()) if isinstance(exc,ValidationError) else 1},
                         ensure_ascii=False,indent=2))
        return 2


if __name__=='__main__':
    sys.exit(main())
