"""Utilities"""

from collections import Counter
import json
import os
import re

import pandas as pd
import roman

import config as cf

def clean_model_name(model_name):
  """Clean the model name for use in filenames."""
  return model_name.replace(".", "")

def get_poem_text_by_fn(fn):
  """
  Get poem text by filename.
  Args:
      fn (str): filename
  Returns:
      str: poem text
  """
  with open(fn, "r") as f:
    return f.read().strip()


def get_humor_message_from_resp(fname):
  """
  Get the humor explanation message from Open AI response.
  Args:
      resp (fname): response file name (processed with `open_ai_client.write_resp_message_to_file`)
  Returns:
      str: humor explanation
  """
  with open(fname, "r") as f:
    resp = f.read().strip()
  return json.loads(resp)["reason"]


# Stylo part ------------------------------------------------------------------

def process_message_for_stylo(fname, md):
  """Based on the metadata at `md`, figure out which corpus the
  message belongs to for Stylo oppose (primary or secondary)"""
  #breakpoint()
  msg_txt = get_humor_message_from_resp(fname)
  # figure out which corpus the message belongs to
  # based on the metadata
  file_id = int(re.sub(r"_[^\n]+$", "",
    os.path.splitext(os.path.basename(fname))[0].replace("humor_", "")))
  has_humor = md.loc[md["id"] == file_id, "comic"].values[0]
  corpus_type = "primary" if bool(has_humor) else "secondary"
  return msg_txt, corpus_type


def message_to_stylo_for_dir(msgdir, stylo_dir, md_file, max_choices=3):
  """Process a directory of responses into Stylo oppose() format."""
  md_df = pd.read_csv(md_file, sep="\t")
  # breakpoint()
  out_primary_list = []
  out_secondary_list = []
  for fname in sorted(os.listdir(msgdir)):
    if not fname.startswith("humor"):
      continue
    choice_nbr = int(re.search(r"_(\d+)\.", fname).group(1))
    assert choice_nbr is not None, f"Choice number not found in {fname}"
    if choice_nbr > max_choices:
      continue
    msg_txt, corpus_type = process_message_for_stylo(
      os.path.join(msgdir, fname), md_df)
    if corpus_type == "primary":
      out_primary_list.append(msg_txt)
    else:
      out_secondary_list.append(msg_txt)

  primary_dir = os.path.join(stylo_dir, "primary_set")
  secondary_dir = os.path.join(stylo_dir, "secondary_set")
  for dname in primary_dir, secondary_dir:
    if not os.path.exists(dname):
      os.makedirs(dname)
  dir_series = primary_dir, secondary_dir
  out_fn_series = "humor_true.txt", "humor_false.txt"
  out_list_series = out_primary_list, out_secondary_list
  for dname, fname, out_list in zip(dir_series, out_fn_series, out_list_series):
    with open(os.path.join(dname, fname), "w") as f:
      f.write("\n".join(out_list))


def clean_century(st):
  clean_st = re.sub(re.compile(r"^\s*Siglo\s*", re.I), "", st)
  return clean_st


# Evaluation ------------------------------------------------------------------

def get_author_info_for_dir(dname):
  """Get author info from a directory of responses."""
  infos = {}
  for fname in os.listdir(dname):
    if not fname.startswith("author"):
      continue
    with open(os.path.join(dname, fname), "r") as f:
      auth_info = json.load(f)
      au_name = auth_info["author"].strip()
      # if "Juana" in au_name:
      #   breakpoint()
      century = clean_century(auth_info["century"].strip())
      try:
        century = int(roman.fromRoman(century))
      except Exception as e:
        century = int(century)
        print(f"Error with century conversion: {e}")
    infos[os.path.basename(fname)] = [au_name, century]
    print(auth_info)
  return infos

def group_judgement_by_prefix(dname):
  """TESt"""
  judgements = {}
  for fname in os.listdir(dname):
    if not fname.startswith("humor"):
      continue
    with open(os.path.join(dname, fname), "r") as f:
      humor_info = json.load(f)
      judgement = humor_info["judgement"].strip()
    prefix = re.sub(r"_\d+\..*$", "", fname)
    if prefix not in judgements:
      judgements[prefix] = []
    judgements[prefix].append(judgement)
  return judgements


def choose_among_disagreeing_judgements(jd):
  """
  Choose a judgement among disagreeing judgements for completions
  for the same poem humor prompt.

  Args:
    jd (dict): Dictionary with judgements for each completion choice

  Returns:
    dict: Dictionary with a chosen judgement per poem id
  """
  chosen_jmts = {}
  for ke, va in jd.items():
    if len(set(va)) != 1:
      # sort by value count in descending order and get first value
      chosen_jmt = sorted(Counter(va).items(), key=lambda x: -x[-1])[0][0]
      chosen_jmts[ke] = chosen_jmt
    else:
      #TODO treat uncertain resposes, so that can evaluate 3-way classification
      chosen_jmts[ke] = va[0] if va[0] != "incierto" else "no"
  return chosen_jmts


def get_judgement_info_for_dir(dname):
  """Get humor true/false judgement from a directory of responses."""
  judgements_for_prefix = {}
  for fname in os.listdir(dname):
    if not fname.startswith("humor"):
      continue
    prefix = re.sub(r"_\d\..*$", "", fname)
    judgements_for_prefix.setdefault(prefix, [])
    with open(os.path.join(dname, fname), "r") as f:
      humor_info = json.load(f)
      judgement = humor_info["judgement"].strip()
      judgements_for_prefix[prefix].append(judgement)
  # analyze judgements
  # for ke, va in judgements_for_prefix.items():
  #   if len(set(va)) != 1:
  #     print(f"  - Diverging judgements for {ke}: {repr(va)}")
  judgements_postpro = choose_among_disagreeing_judgements(judgements_for_prefix)
  return judgements_postpro