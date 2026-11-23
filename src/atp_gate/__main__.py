"""ATP Gate: fail-closed paper decisions and separate historical research commands."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError
from pydantic import ValidationError

from .contracts import DecisionInput
from .historical_audit import audit_tennis_data_csv
from .policy import evaluate


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
    research_train=sub.add_parser('research-train',help='XGBoost research with chronological split; NO live allocation')
    research_train.add_argument('paths',nargs='+')
    research_train.add_argument('--out',required=True,help='JSON research report output path')
    research_train.add_argument('--minimum-total',type=int,default=200)
    research_train.add_argument('--minimum-target',type=int,default=30)
    research_train.add_argument('--seed',type=int,default=20261123)
    args=parser.parse_args()

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

    try:
        if args.cmd=='audit':
            print(json.dumps(audit_tennis_data_csv(args.path),ensure_ascii=False,indent=2))
            return 0
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
