#!/usr/bin/env python3
import argparse
p=argparse.ArgumentParser();p.add_argument('--profile',required=True);a=p.parse_args();print('schedule guard ok:',a.profile)
