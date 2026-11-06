from __future__ import annotations

from openpyxl import Workbook,load_workbook

from scripts.exclusion_memory import evaluate,add_sheet,similarity


def fake_book():
    wb=Workbook()
    d=wb.active
    d.title="Dropped"
    d.append(["Route","Status","Reason","Source ID"])
    d.append(["Copenhagen robotics PhD","CLOSED","Award expired","N1"])
    n=wb.create_sheet("Not added")
    n.append(["Route","Why not"])
    n.append(["Deep Learning for Medical Image Segmentation with Aerial Robotics",
              "Previous call restricted to citizens, needs re-check if reissued"])
    return wb


def test_exact_id_produces_warning_not_block():
    report=evaluate(fake_book(),[{"id":"N1","title":"Copenhagen robotics PhD 2027",
                                  "url":"https://example.edu/2027"}])
    assert report["original_records"]==2
    assert report["potential_reappearances"][0]["match_type"]=="source_id_exact"
    assert report["potential_reappearances"][0]["decision"]=="review_current_call; do_not_block_automatically"


def test_similarity_is_conservative():
    score,n=similarity("Deep Learning for Medical Image Segmentation with Aerial Robotics",
                       "Deep Learning for Medical Image Segmentation with Aerial Robotics")
    assert score==1.0
    assert n>=4
    score,n=similarity("PhD in Robotics","PhD in Robotics")
    assert score==1.0 and n==1
    report=evaluate(fake_book(),[{"id":"N2","title":"Deep Learning for Medical Image Segmentation with Aerial Robotics",
                                  "url":"https://example.edu/new"}])
    assert report["potential_reappearances"][0]["match_type"]=="title_similarity_warning_only"


def test_history_worksheet_is_regenerated_without_modifying_original(tmp_path):
    wb=fake_book()
    base=wb["Dropped"]["C2"].value
    report=evaluate(wb,[])
    add_sheet(wb,report)
    add_sheet(wb,report)
    assert wb["Dropped"]["C2"].value==base
    assert wb["Exclusion memory"].max_row==3
    path=tmp_path/"archive.xlsx"
    wb.save(path)
    assert load_workbook(path)["Exclusion memory"].max_row==3
