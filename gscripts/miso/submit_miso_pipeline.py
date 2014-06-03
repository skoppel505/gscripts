#!/usr/bin/env python
# coding=utf-8

# Parse command line arguments
import argparse

# Submit jobs to the cluster
from gscripts.qtools import Submitter

# File name manipulations
import os

# The program that does all the heavy lifting of creating the submitter scripts
from gscripts.miso import MisoPipeline


'''
Author: olga
Date created: 7/12/13 9:38 AM

The purpose of this program is to write submitter scripts to perform MISO
analysis on a large amount of files. This script assumes paired-end reads.

# **Note** for some reason,

Example runs:

submit_miso_pipeline.py --psi-only --paired-end --event-type SE \
--sample-info-file ~/projects/singlecell/singlecell/sample_info.txt \
--sh-scripts-dir ~/projects/singlecell/scripts/ \
--summary-output-dir-base ~/projects/singlecell/singlecell/analysis/ \
--psi-walltime '0:50:00' --annotation-index-strfmt \
'/home/yeo-lab/genomes/hg19/miso_annotations/%s_index' \
--sample-id-suffix min10reads \
--extra-miso-arguments ' --settings-filename \
~/MISO/misopy/settings/miso_settings_min_event_reads10.txt' \
--individual-jobs

submit_miso_pipeline.py --psi-only --paired-end --event-type SE --sample-info-file ~/projects/singlecell/singlecell/sample_info_round2and3.txt --sh-scripts-dir ~/projects/singlecell/scripts/ --summary-output-dir-base ~/projects/singlecell/singlecell/analysis/ --psi-walltime '1:50:00' --annotation-index-strfmt '/home/yeo-lab/genomes/hg19/miso_annotations/%s_index' --sample-id-suffix min10reads --extra-miso-arguments ' --settings-filename ~/MISO/misopy/settings/miso_settings_min_event_reads10.txt' --individual-jobs

submit_miso_pipeline.py --psi-only --single-end --event-type SE \
--sample-info-file ~/projects/singlecell/singlecell/sample_info.txt \
--sh-scripts-dir ~/projects/singlecell/scripts/ \
--summary-output-dir-base ~/projects/singlecell/singlecell/analysis/ \
--psi-walltime '0:50:00' \
--annotation-index-strfmt '/home/obotvinnik/genomes/hg19/miso_annotations/%s_index'


submit_miso_pipeline.py --run-all --single-bam $BAM $SAMPLE_ID\
--num-processes 16

TODO: deprecate the non-queue way of running
'''

# Class: CommandLine
class CommandLine(object):
    def __init__(self, inOpts=None):
        self.parser = argparse.ArgumentParser(
            description='''Write submitter scripts to perform MISO analysis
            on individual samples. This script assumes paired-end reads.
            ''',
            add_help=True, prefix_chars='-')


        read_type = self.parser.add_mutually_exclusive_group(required=True)
        read_type.add_argument('--paired-end', action='store_const',
                               dest='read_type', const='paired_end',
                               help='Indicates that these are paired-end '
                                    'reads. This is the default. Can compute '
                                    'insert size using "--insert-len" or '
                                    '"--run-all" options')
        read_type.add_argument('--single-end', action='store_const',
                               dest='read_type', const='single_end',
                               help='Indicates that these reads are '
                                    'single-ended, and treats them as such. '
                                    'Does not compute insert size.')

        samples = self.parser.add_mutually_exclusive_group(required=True)
        samples.add_argument('--bam', type=str,
                             action='store', default='',
                             help='A single BAM file')

        # self.parser.add_argument('--annotation-index-strfmt',
        #                          type=str, action='store',
        #                          help='A "strfmt" type string describing '
        #                               'where the **indexed** MISO annotations'
        #                               ' are housed, where the "%s" is where the'
        #                               ' event type will be. The default is '
        #                               '/projects/ps-yeolab/genomes/hg19/ASS_MISO/ASS_MISO_%s/ '
        #                               'so if the event type is SE, '
        #                               'then the indexed MISO annotations are '
        #                               'in '
        #                               '/projects/ps-yeolab/genomes/hg19/ASS_MISO/ASS_MISO_SE/',
        #                          default='/projects/ps-yeolab/genomes/hg19/ASS_MISO')
        # self.parser.add_argument('--constitutive-exon-gff', type=str,
        #                          action='store',
        #                          default='/home/obotvinnik/genomes/hg19/miso_annotations/SE_constitutive/SE.hg19.min_20.const_exons.gff',
        #                          help='Location of the gff file of '
        #                               'constitutive exons, generated by '
        #                               'pe_utils.py of MISO')
        self.parser.add_argument('--debug', action='store_true',
                                 default=False,
                                 help="Don't make any files, just print "
                                      "everything that would have been made")
        self.parser.add_argument('--event-type', '-e',
                                 default='',
                                 action='store', type=str, required=False,
                                 help="Which event you'd like to index. One "
                                      "of:" +
                                      ('\n'
                                       '1. Skipped exons (SE)\n'
                                       '2. Alternative 3’/5’ splice sites ('
                                       'A3SS, A5SS)\n'
                                       '3. Mutually exclusive exons (MXE)\n'
                                       '4. Tandem 3’ UTRs (TandemUTR)\n'
                                       '5. Retained introns (RI)\n'
                                       '6. Alternative first exons (AFE)\n'
                                       '7. Alternative last exons (ALE)\n'
                                       '                                      '
                                      ) +
                                      "See http://genes.mit"
                                      ".edu/burgelab/miso/docs/#alternative-event-annotations for more information")
        self.parser.add_argument('--extra-miso-arguments', type=str,
                                 action='store',
                                 default='',
                                 help='Any additional MISO "compute psi" '
                                      'arguments you want'
                                      ' to supply to all the samples. The '
                                      'default is no additional arguments. '
                                      'Protect this argument with quotes so '
                                      'it does not get interpreted as an '
                                      'argument to the MISO pipeline script, '
                                      'e.g. --extra-miso-arguments " '
                                      '--no-filter-events'
                                      ' --settings-filename '
                                      'miso_settings_min_event_reads5.txt". '
                                      'If this is not working for you, '
                                      'try adding a space between the first '
                                      'quote and the first dash of the miso '
                                      'argument. For some reason this helps..'
                                      '..')
        self.parser.add_argument('--genome', type=str, action='store',
                                 required=True, help='Which genome to use')
        self.parser.add_argument('--individual-jobs', #type=bool,
                                 action='store_true',
                                 default=False,
                                 help='Whether or not to put every job as an '
                                      'individual script. If flagged, '
                                      'yes. Otherwise, run as an array job. '
                                      'This only applies for psi and summary '
                                      'jobs. Insert length jobs will still be run as array jobs regardless.')
        self.parser.add_argument('--miso-scripts-dir', type=str,
                                 action='store',
                                 help='Which directory to use as the prefix for '
                                      'miso scripts. Default is the directory'
                                      ' returned from the unix command line '
                                      'command "which miso".', required=False)
        self.parser.add_argument('--num-processes', '-p', type=int,
                                 action='store', default=16,
                                 help='Number of subprocesses for MISO to run'
                                      '. If you are using a computing cluster'
                                      ' with several processors on a single '
                                      'node, use the number of processors '
                                      'you are requesting')
        # self.parser.add_argument('--num-cores', type=int,
        #                          action='store', default=1,
        #                          help='Number of cores to distribute the '
        #                               'computation to. The default is 1. If '
        #                               'the number of cores is greater than 1,'
        #                               ' then make the psi and summary jobs a '
        #                               'job array.')
        self.parser.add_argument('--output-sh', type=str, required=True,
                                 action='store',
                                 help="The name of the .sh script created for one-touch action")

        self.parser.add_argument('--sample-id', type=str,
                                 action='store',
                                 help='sample ID. required if using --bam',
                                 required=False)
        self.parser.add_argument('--sample-id-suffix', type=str,
                                 action='store', default='',
                                 help='Extra identification to add to these '
                                      'samples, e.g. if you are running with '
                                      'a settings file that specifies a '
                                      'minimum of 10 reads instead of 20, '
                                      'you could say "_min_event_reads10" as '
                                      'a suffix')

        self.parser.add_argument('--submit-sh-suffix', type=str,
                                 action='store',
                                 default='',
                                 help='Add a suffix to this '
                                      'script name, and the stderr/stdout '
                                      'produced'
                                      ' by the PBS job, too. The default is '
                                      'miso_[event_type].sh, for example if '
                                      'your event type is skipped exons (SE),'
                                      ' then the script is called miso_SE.sh '
                                      'If you add the argument '
                                      '"--submit-sh-suffix pooled" then the '
                                      'submit filename would be '
                                      '"miso_pooled_SE.sh"')
        self.parser.add_argument('--summary-walltime', type=str,
                                 action='store',
                                 default='00:50:00',
                                 help='How much time to tell the cluster to '
                                      'allow the summarization job to run.')
        self.parser.add_argument('--summary-output-dir-base', type=str,
                                 action='store', default='',
                                 help='The base directory for which to place '
                                      'the MISO summary outputs. By '
                                      'default, MISO outputs are of '
                                      'the format: (base_dir)/miso/('
                                      'event_type)/(sample_id). The default '
                                      'base dir is the directory of the .bam '
                                      'file, e.g. if the bam you provide is '
                                      'in ~/scratch/single_cell and your '
                                      'event type is "SE", then miso outputs '
                                      'for sample id "A1_02"'
                                      ' will be in the folder'
                                      '~/scratch/single_cell/miso/SE/A1_02/. '
                                      'However, the intermediate output would'
                                      ' still be in (bam_dir)/miso/('
                                      'event_type)/(sample_id) because MISO '
                                      'outputs a TON of intermediate files '
                                      'that nobody wants to deal with.'
                                      'Otherwise, if you provide a folder '
                                      'such as '
                                      '~/projects/single_cell/analysis, '
                                      'then the MISO summary output for the '
                                      'same '
                                      'sample would be in: '
                                      '~/projects/single_cell/analysis/miso/SE/A1_02')

        if inOpts is None:
            self.args = vars(self.parser.parse_args())
        else:
            self.args = vars(self.parser.parse_args(inOpts))

    def do_usage_and_die(self, str):
        '''
        If a critical error is encountered, where it is suspected that the
        program is not being called with consistent parameters or data, this
        method will write out an error string (str), then terminate execution
        of the program.
        '''
        import sys

        print >> sys.stderr, str
        self.parser.print_usage()
        return 2


# Class: Usage
class Usage(Exception):
    '''
    Used to signal a Usage error, evoking a usage statement and eventual
    exit when raised
    '''

    def __init__(self, msg):
        self.msg = msg


# Function: main
def main():
    '''
    This function is invoked when the program is run from the command line,
    i.e. as:
        python submit_miso_pipeline.py
    or as:
        ./submit_miso_pipeline.py
    If the user has executable permissions on the user (set by chmod ug+x
    program.py or by chmod 775 program py. Just need the 4th bit set to true)
    '''
    cl = CommandLine()
    try:
        miso_pipeline = MisoPipeline(cl.args['bam'], cl.args['sample_id'],
                                     cl.args['output_sh'], cl.args['genome'],
                                     cl.args['annotation_index_strfrmt'],
                                     cl.args['constitutive_exon_gff'],
                                     read_type=cl.args['read_type'],
                                     debug=cl.args['debug'],
                                     num_processes=cl.args['num_processes'],
                                     submit_sh_suffix=cl.args[
                                         'submit_sh_suffix'],
                                     sample_id_suffix=cl.args[
                                         'sample_id_suffix'],
                                     extra_miso_arguments=cl.args[
                                         'extra_miso_arguments'])

        # Read the arguments to see which piece of the MISO pipeline to run
        #if cl.args['run_all']:
        #    if cl.args['single_sample']:
        miso_pipeline.run_all_single_sample()
        #else:
        #    miso_pipeline.run_all()
        #elif cl.args['insert_len_only']:
        #    miso_pipeline.insert_len()
        #elif cl.args['psi_only']:
        #    miso_pipeline.psi()
        #elif cl.args['summary_only']:
        #    miso_pipeline.summary()
        #elif cl.args['psi_and_summary']:
        #    miso_pipeline.psi_and_summary()

    # If not all the correct arguments are given, break the program and
    # show the usage information
    except Usage, err:
        cl.do_usage_and_die(err.msg)


if __name__ == '__main__':
    main()