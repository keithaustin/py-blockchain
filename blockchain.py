import hashlib
import json
import requests
from textwrap import dedent
from time import time
from uuid import uuid4
from urllib.parse import urlparse

from flask import Flask, jsonify, request
from flask.wrappers import Request

class Blockchain(object):
    # Constructor
    def __init__(self):
        self.chain = []
        self.curr_transactions = []

        # Create empty node set
        self.nodes = set()

        # Create genesis block
        self.new_block(previous_hash=1, proof=100)

    # Register a new node on the network
    def register_node(self, address):
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    # Create a new block
    def new_block(self, proof, previous_hash=None):

        # Create block
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.curr_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # Reset transaction list
        self.curr_transactions = []

        # Add block to chain
        self.chain.append(block)
        return block
    
    # Create new transaction
    def new_transaction(self, sender, recipient, amount):
        self.curr_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    # Proof of Work algorithm
    def proof_of_work(self, last_proof):
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof

    # Validate a chain
    def valid_chain(self, chain):
        last_block = chain[0]
        curr_index = 1

        while curr_index < len(chain):
            block = chain[curr_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n------------\n")
            
            # Check hash for correctness
            if block['previous_hash'] != self.hash(last_block):
                return False

            # Check for correct Proof of Work
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block 
            curr_index += 1

        return True

    def resolve_conflicts(self):
        neighbors = self.nodes
        new_chain = None

        # Look for only chains longer than ours
        min_length = len(self.chain)

        # Get and verify chains from all nodes
        for node in neighbors:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # Check if length is longer and chain is valid
                if length > min_length and self.valid_chain(chain):
                    min_length = length
                    new_chain = chain

        # Replace our chain if a new, longer, valid chain is found
        if new_chain:
            self.chain = new_chain
            return True

        return False
            

    # Validate a proof
    @staticmethod
    def valid_proof(last_proof, proof):
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000";

    # Hash a block
    @staticmethod
    def hash(block):
        # Dump block data to string, ensuring proper ordering
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()
    
    # Contains data about the last block in the chain
    @property
    def last_block(self):
        return self.chain[-1]


# Create a node and give it a unique address
app = Flask(__name__)
node_id = str(uuid4()).replace('-', '')

# Instantiate the blockchain
blockchain = Blockchain()

# Routes

# Mines new blocks
@app.route('/mine', methods=['GET'])
def mine():
    # Run Proof of Work
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # Create a transaction to reward user
    # Sender is "0" to signify this coin was mined
    blockchain.new_transaction(
        sender="0",
        recipient=node_id,
        amount=1
    )

    # Add new block to chain
    prev_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, prev_hash)

    response = {
        'message': "New Block Created",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200

# Creates a new transaction
@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    # Get request data
    values = request.get_json()

    # Check that required fields are present
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing data', 400

    # Create the transaction
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201

# Shows the full blockchain
@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

# Registers a new node on the network
@app.route('/nodes/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201

# Resolves a node on the network
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain,
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain,
        }

    return jsonify(response), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)