
import sys, argparse
from os.path import dirname, abspath, exists

sys.path.insert(0,dirname( abspath(__file__))+"/sitemap/")
import generate
import private

parser = argparse.ArgumentParser(description='Index data for a sphinx server.')
parser.add_argument('server', type=str, help='Server address.')
parser.add_argument('part', type=int, help='Server number.')
parser.add_argument('--output', type=str, help='Output folder.', default=None)
parser.add_argument('--batch_size', type=str, help='Mongo batch fetch size.', default=10240)

params = parser.parse_args()

generate.generate(params.server, params.part, {}, params.batch_size, params.output)
